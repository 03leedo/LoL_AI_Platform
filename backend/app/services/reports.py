"""AI/rule-based summary report over recent matches (M3).

Pipeline: load records + event history → detect patterns (rules) → compose a
deterministic Korean report → optionally have the LLM rewrite the prose
(patterns and numbers stay rule-computed) → cache by
(report version, metric version, window, latest match id).
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.analysis import (
    fetch_player_event_history,
    fetch_player_match_records,
    get_cached_report,
    save_report,
)
from app.services.custom_metrics import METRIC_VERSION
from app.services.llm_provider import LlmProviderError, generate_json, provider_available
from app.services.patterns import (
    RECOMMENDATIONS_BY_KEY,
    detect_patterns,
    summarize_death_autopsy,
)
from app.services.role_analyzer import build_role_analysis
from app.services.scorecard import build_scorecard

logger = logging.getLogger(__name__)

REPORT_VERSION = 1
MIN_GAMES_FOR_REPORT = 3

ROLE_LABELS = {
    "TOP": "탑",
    "JUNGLE": "정글",
    "MIDDLE": "미드",
    "BOTTOM": "원딜",
    "UTILITY": "서포터",
}

LLM_SYSTEM_PROMPT = (
    "너는 리그 오브 레전드 경기 후 복기 코치다. 입력 JSON에 들어 있는 수치와 패턴만 근거로 사용하고, "
    "새로운 사실이나 수치를 만들어내지 마라. 플레이어의 의도를 단정하지 말고 '~하는 경향', '~일 가능성' 화법을 사용하라. "
    "각 항목에서 입력의 stat 값을 자연스럽게 인용하라. 반드시 다음 키를 가진 JSON 객체만 출력하라: "
    '{"summary": "3문장 이내 종합 요약", "strengths": ["최대 3개"], "weaknesses": ["최대 3개"], '
    '"recommendations": ["최대 4개, 구체적 행동 지침"]} 모든 텍스트는 한국어.'
)


async def get_or_create_report(
    db: AsyncSession,
    puuid: str,
    window: int,
    force: bool = False,
) -> dict[str, Any]:
    records = await fetch_player_match_records(db=db, puuid=puuid, limit=window)
    games = len(records)
    window_key = f"recent{window}"

    if games < MIN_GAMES_FOR_REPORT:
        return {
            "puuid": puuid,
            "window": window_key,
            "games_analyzed": games,
            "needs_ingest": True,
            "generated_by": "rules",
            "cached": False,
            "cache_key": "",
            "summary": "리포트를 만들기엔 수집된 경기가 부족합니다. 먼저 랭크 분석에서 최근 경기를 수집해 주세요.",
            "strengths": [],
            "weaknesses": [],
            "recommendations": [],
            "patterns": [],
            "autopsy": None,
        }

    latest_match_id = records[0]["match_id"]
    cache_key = f"v{REPORT_VERSION}:m{METRIC_VERSION}:{window_key}:{latest_match_id}"

    if not force:
        cached = await get_cached_report(db=db, puuid=puuid, cache_key=cache_key)
        if cached is not None and cached.content:
            return {**cached.content, "cached": True, "cache_key": cache_key}

    event_history = await fetch_player_event_history(
        db=db, puuid=puuid, match_ids=[record["match_id"] for record in records]
    )
    scorecard = build_scorecard(records)
    role_analysis = build_role_analysis(records)
    patterns = detect_patterns(records, event_history)
    autopsy = summarize_death_autopsy(event_history)

    content = build_deterministic_report(
        puuid=puuid,
        window_key=window_key,
        records=records,
        scorecard=scorecard,
        role_analysis=role_analysis,
        patterns=patterns,
        autopsy=autopsy,
    )

    if provider_available():
        try:
            content = await enrich_report_with_llm(content, scorecard, role_analysis)
        except LlmProviderError as exc:
            logger.warning("LLM report skipped for %s: %s", puuid, exc)

    try:
        await save_report(
            db=db,
            puuid=puuid,
            cache_key=cache_key,
            window=window_key,
            generated_by=content["generated_by"],
            content=content,
        )
    except Exception as exc:  # pragma: no cover - report should still be returned
        logger.warning("Report cache persistence skipped for %s: %s", puuid, exc)
        try:
            await db.rollback()
        except Exception:  # pragma: no cover
            pass

    return {**content, "cached": False, "cache_key": cache_key}


def build_deterministic_report(
    puuid: str,
    window_key: str,
    records: list[dict[str, Any]],
    scorecard: dict[str, Any],
    role_analysis: dict[str, Any],
    patterns: list[dict[str, Any]],
    autopsy: dict[str, Any],
) -> dict[str, Any]:
    games = len(records)
    wins = sum(1 for record in records if record.get("win"))
    win_rate = wins / games if games else 0.0

    weaknesses = [p for p in patterns if p["severity"] in {"warn", "critical"}]
    strengths = [p for p in patterns if p["severity"] == "positive"]

    recommended_roles = [ROLE_LABELS.get(role, role) for role in role_analysis.get("recommended", [])]

    summary_parts = [f"최근 {games}경기 승률 {win_rate:.0%}."]
    if recommended_roles:
        summary_parts.append(f"추천 포지션은 {'/'.join(recommended_roles)}입니다.")
    if strengths:
        summary_parts.append(f"가장 뚜렷한 강점은 '{strengths[0]['title']}'입니다.")
    if weaknesses:
        summary_parts.append(f"개선이 가장 시급한 부분은 '{weaknesses[0]['title']}'입니다.")

    recommendations: list[str] = []
    for pattern in weaknesses[:4]:
        advice = RECOMMENDATIONS_BY_KEY.get(pattern["key"])
        if advice:
            recommendations.append(advice)

    return {
        "puuid": puuid,
        "window": window_key,
        "games_analyzed": games,
        "needs_ingest": False,
        "generated_by": "rules",
        "summary": " ".join(summary_parts),
        "strengths": [f"{p['title']} ({p['stat']})" for p in strengths[:3]],
        "weaknesses": [f"{p['title']} ({p['stat']})" for p in weaknesses[:3]],
        "recommendations": recommendations,
        "patterns": patterns,
        "autopsy": autopsy,
    }


async def enrich_report_with_llm(
    content: dict[str, Any],
    scorecard: dict[str, Any],
    role_analysis: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "sample": {"games": content["games_analyzed"], "window": content["window"]},
        "scorecard": scorecard,
        "roles": role_analysis,
        "patterns": [
            {k: v for k, v in pattern.items() if k != "matches"}
            for pattern in content["patterns"]
        ],
        "autopsy": content["autopsy"],
        "rule_based_draft": {
            "summary": content["summary"],
            "strengths": content["strengths"],
            "weaknesses": content["weaknesses"],
            "recommendations": content["recommendations"],
        },
    }

    generated = await generate_json(LLM_SYSTEM_PROMPT, payload)
    sanitized = _sanitize_llm_report(generated)
    if sanitized is None:
        raise LlmProviderError("LLM report failed validation")

    return {**content, **sanitized, "generated_by": "llm"}


def _sanitize_llm_report(generated: dict[str, Any]) -> dict[str, Any] | None:
    summary = generated.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return None

    def _string_list(value: Any, limit: int) -> list[str] | None:
        if not isinstance(value, list):
            return None
        items = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        return items[:limit]

    strengths = _string_list(generated.get("strengths"), 3)
    weaknesses = _string_list(generated.get("weaknesses"), 3)
    recommendations = _string_list(generated.get("recommendations"), 4)
    if strengths is None or weaknesses is None or recommendations is None:
        return None

    return {
        "summary": summary.strip(),
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
    }
