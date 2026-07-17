"""AI/rule-based summary report over recent matches (M3).

Pipeline: load records + event history → detect patterns (rules) → compose a
deterministic Korean report → optionally have the LLM rewrite the prose
(patterns and numbers stay rule-computed) → cache by
(report version, metric version, window, latest match id).
"""

import json
import logging
import re
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
    REPLAY_QUESTIONS_BY_KEY,
    detect_patterns,
    summarize_death_autopsy,
)
from app.services.role_analyzer import build_role_analysis
from app.services.scorecard import build_scorecard

logger = logging.getLogger(__name__)

# v2: limitations + replay_questions (Phase 1)
# v3: queue-filtered aggregation + analyzable-death denominator (Phases 2/3)
# v4: evidence-grounded LLM contract — observations/hypotheses with enforced
#     refs, numeric-hallucination guard, rule-owned strengths/weaknesses (Phase 6)
REPORT_VERSION = 4
REPORT_PROMPT_VERSION = 2
MIN_GAMES_FOR_REPORT = 3
DEFAULT_QUEUE_ID = 420  # ranked solo

MAX_OBSERVATIONS = 4
MAX_HYPOTHESES = 3
MAX_PRACTICE_SUGGESTIONS = 3
# Small integers appear naturally in prose (enumeration, "5분 윈도우"); only
# larger numbers must be traceable to the payload.
FREE_NUMBER_MAX = 10

STANDARD_REPORT_LIMITATIONS = [
    "모든 수치는 Riot API 데이터 기반 관측이며, 장면의 의도나 팀 상황은 리플레이 확인 전에는 판정하지 않습니다.",
    "타임라인 위치·골드는 1분 단위 근사입니다(±60초).",
]

ROLE_LABELS = {
    "TOP": "탑",
    "JUNGLE": "정글",
    "MIDDLE": "미드",
    "BOTTOM": "원딜",
    "UTILITY": "서포터",
}

LLM_SYSTEM_PROMPT = (
    "너는 리그 오브 레전드 경기 후 복기 코치다. 입력 JSON에 들어 있는 수치와 패턴만 근거로 사용하고, "
    "새로운 사실이나 수치를 만들어내지 마라. 문장에 쓰는 모든 숫자는 입력에 실제로 존재해야 한다. "
    "플레이어의 의도를 단정하지 말고, 관측(사실)과 가설(해석 후보)을 분리하라. "
    "반드시 다음 형식의 JSON 객체만 출력하라: "
    '{"insufficient": false, "summary": "3문장 이내 종합 요약", '
    '"observations": [{"text": "입력 패턴을 인용한 사실 서술", "refs": ["pat:패턴키 또는 매치ID"]}], '
    '"hypotheses": [{"text": "\'~일 수 있다\' 화법의 해석 후보", "refs": ["근거 id"]}], '
    '"practice_suggestions": ["다음 몇 판 동안 시도할 실험 + 확인할 지표"]} '
    "규칙: observations 최대 4개(각각 refs 필수 — 입력 payload의 pattern id나 match id만 사용), "
    "hypotheses 최대 3개, practice_suggestions 최대 3개(명령이 아니라 실험 제안으로). "
    '입력의 근거가 리포트를 쓰기에 부족하면 다른 키 없이 {"insufficient": true, "reason": "짧은 이유"}만 출력하라. '
    "모든 텍스트는 한국어."
)


async def get_or_create_report(
    db: AsyncSession,
    puuid: str,
    window: int,
    force: bool = False,
    queue: int | None = DEFAULT_QUEUE_ID,
) -> dict[str, Any]:
    records = await fetch_player_match_records(
        db=db,
        puuid=puuid,
        limit=window,
        queue_ids=[queue] if queue else None,
    )
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
            "observations": [],
            "hypotheses": [],
            "limitations": [],
            "replay_questions": [],
            "patterns": [],
            "autopsy": None,
        }

    latest_match_id = records[0]["match_id"]
    cache_key = f"v{REPORT_VERSION}:m{METRIC_VERSION}:q{queue or 0}:{window_key}:{latest_match_id}"

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
    replay_questions: list[str] = []
    for pattern in weaknesses[:4]:
        advice = RECOMMENDATIONS_BY_KEY.get(pattern["key"])
        if advice:
            recommendations.append(advice)
        question = REPLAY_QUESTIONS_BY_KEY.get(pattern["key"])
        if question and len(replay_questions) < 3:
            replay_questions.append(question)

    limitations = list(STANDARD_REPORT_LIMITATIONS)
    limitations.append(
        f"표본 {games}경기 기준입니다. 이 리포트의 평균 점수는 단순 평균이라 표본이 적을수록 신뢰도가 낮습니다"
        " (포지션 적합도만 표본 보정이 적용됩니다)."
    )
    if (autopsy or {}).get("objective_analyzable_deaths"):
        limitations.append(
            "'데스 후 오브젝트 획득 동반률'의 분모는 오브젝트가 살아 있거나 90초 내 생성 예정이던 "
            "'분석 가능 데스'만 포함합니다. 오브젝트 생성 시각은 패치 근사 규칙으로 계산됩니다."
        )

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
        "observations": [],
        "hypotheses": [],
        "limitations": limitations,
        "replay_questions": replay_questions,
        "patterns": patterns,
        "autopsy": autopsy,
    }


async def enrich_report_with_llm(
    content: dict[str, Any],
    scorecard: dict[str, Any],
    role_analysis: dict[str, Any],
) -> dict[str, Any]:
    """LLM contract v2 (Phase 6): the model may only rephrase and organize —
    every observation must reference an id that exists in the payload, and any
    number it writes must already appear in the payload. Strengths, weaknesses,
    limitations, and replay questions stay rule-owned and cannot be overwritten.
    """
    payload, known_refs = _build_llm_payload(content, scorecard, role_analysis)
    logger.info(
        "Report LLM call: prompt_version=%s refs=%d", REPORT_PROMPT_VERSION, len(known_refs)
    )

    payload_numbers = _numbers_in(json.dumps(payload, ensure_ascii=False))
    generated = await generate_json(LLM_SYSTEM_PROMPT, payload)

    if isinstance(generated, dict) and generated.get("insufficient") is True:
        reason = str(generated.get("reason") or "").strip()[:200]
        # The reason is LLM-authored text shown to the user — the same
        # numeric-hallucination guard applies (domain review M1, 2026-07-14).
        if not reason or not _statement_numbers_ok(reason, payload_numbers):
            reason = "모델이 근거 부족으로 서술을 생략했습니다."
        return {
            **content,
            "generated_by": "rules",
            "llm_prompt_version": REPORT_PROMPT_VERSION,
            "llm_insufficient_reason": reason,
        }
    sanitized = _sanitize_llm_statements(generated, known_refs, payload_numbers)
    if sanitized is None:
        raise LlmProviderError("LLM report failed validation")

    merged = {
        **content,
        "generated_by": "llm",
        "llm_prompt_version": REPORT_PROMPT_VERSION,
        "summary": sanitized["summary"],
        "observations": sanitized["observations"],
        "hypotheses": sanitized["hypotheses"],
    }
    if sanitized["practice_suggestions"]:
        merged["recommendations"] = sanitized["practice_suggestions"]
    return merged


def _build_llm_payload(
    content: dict[str, Any],
    scorecard: dict[str, Any],
    role_analysis: dict[str, Any],
) -> tuple[dict[str, Any], set[str]]:
    known_refs: set[str] = set()
    patterns_payload: list[dict[str, Any]] = []
    for pattern in content.get("patterns", []):
        pattern_id = f"pat:{pattern['key']}"
        known_refs.add(pattern_id)
        match_ids = list(pattern.get("matches", []))[:3]
        known_refs.update(match_ids)
        patterns_payload.append(
            {
                "id": pattern_id,
                "severity": pattern["severity"],
                "title": pattern["title"],
                "description": pattern["description"],
                "stat": pattern.get("stat"),
                "matches": match_ids,
            }
        )

    payload = {
        "sample": {"games": content["games_analyzed"], "window": content["window"]},
        "scorecard": scorecard,
        "roles": role_analysis,
        "patterns": patterns_payload,
        "autopsy": content.get("autopsy"),
        "rule_summary": content.get("summary"),
    }
    return payload, known_refs


_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


def _numbers_in(text: str) -> set[str]:
    allowed: set[str] = set()
    for token in _NUMBER_RE.findall(text):
        allowed.add(token)
        try:
            value = float(token)
        except ValueError:
            continue
        if value.is_integer():
            allowed.add(str(int(value)))
        if 0 < value <= 1:
            # Ratios in the payload are commonly written as percents in prose.
            allowed.add(str(int(round(value * 100))))
    return allowed


def _statement_numbers_ok(text: str, payload_numbers: set[str]) -> bool:
    for token in _NUMBER_RE.findall(text):
        value = float(token)
        if value.is_integer() and value <= FREE_NUMBER_MAX:
            continue
        if token in payload_numbers:
            continue
        if value.is_integer() and str(int(value)) in payload_numbers:
            continue
        return False
    return True


def _sanitize_llm_statements(
    generated: dict[str, Any],
    known_refs: set[str],
    payload_numbers: set[str],
) -> dict[str, Any] | None:
    summary = generated.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        return None
    if not _statement_numbers_ok(summary, payload_numbers):
        logger.warning("LLM summary rejected: unsupported number")
        return None

    def statements(value: Any, limit: int, require_refs: bool) -> list[dict[str, Any]] | None:
        if value is None:
            return []
        if not isinstance(value, list):
            return None
        items: list[dict[str, Any]] = []
        for raw in value:
            if not isinstance(raw, dict):
                continue
            text = raw.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            refs_raw = raw.get("refs")
            refs = [r for r in refs_raw if isinstance(r, str)] if isinstance(refs_raw, list) else []
            if any(ref not in known_refs for ref in refs):
                logger.warning("LLM statement dropped: unknown ref")
                continue
            if require_refs and not refs:
                logger.warning("LLM observation dropped: missing refs")
                continue
            if not _statement_numbers_ok(text, payload_numbers):
                logger.warning("LLM statement dropped: unsupported number")
                continue
            items.append({"text": text.strip(), "refs": refs})
            if len(items) >= limit:
                break
        return items

    observations = statements(generated.get("observations"), MAX_OBSERVATIONS, require_refs=True)
    hypotheses = statements(generated.get("hypotheses"), MAX_HYPOTHESES, require_refs=False)
    if observations is None or hypotheses is None:
        return None

    suggestions: list[str] = []
    suggestions_raw = generated.get("practice_suggestions")
    if isinstance(suggestions_raw, list):
        for raw in suggestions_raw:
            if isinstance(raw, str) and raw.strip() and _statement_numbers_ok(raw, payload_numbers):
                suggestions.append(raw.strip())
            if len(suggestions) >= MAX_PRACTICE_SUGGESTIONS:
                break

    return {
        "summary": summary.strip(),
        "observations": observations,
        "hypotheses": hypotheses,
        "practice_suggestions": suggestions,
    }
