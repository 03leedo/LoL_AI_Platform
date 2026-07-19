"""Evidence-safe analysis semantics (Phase 1, FABLE_EXECUTION_PLAN).

Layers on top of rule-computed analysis WITHOUT touching any metric formula:

- deterministic evidence IDs so every factual claim is traceable;
- statement structure separating observation / hypothesis / limitation /
  replay_question (domain invariant #1);
- direction groups so risk/style signals are not displayed as ability scores
  (PRODUCT_ANALYSIS_SPEC §7.1).
"""

from typing import Any

SEMANTICS_VERSION = 2

STATEMENT_KINDS = {"observation", "hypothesis", "limitation", "replay_question"}

# PRODUCT_ANALYSIS_SPEC §7.1 — 점수 방향이 섞이지 않도록 두 그룹으로 분리.
PERFORMANCE_METRICS = {
    "objective_setup_score",
    "lead_conversion_score",
    "stability_score",
    "teamfight_persistence_score",
}
RISK_STYLE_METRICS = {
    "death_cost_index",
    "throw_index",
    "gold_retention_score",
    "gambler_index",
    "death_acceleration_index",
}

# Evidence kinds whose anchored moments are worth a replay pass.
REPLAY_WORTHY_KINDS = {"death_cost", "throw_index", "gambler", "death_chain"}
MAX_REPLAY_QUESTIONS = 3

STANDARD_LIMITATIONS = [
    "타임라인은 1분 단위 프레임이라 위치·골드 기반 판정에는 최대 ±60초 오차가 있습니다.",
    "체력은 1분 단위 스냅샷만 확인할 수 있고 스킬/스펠 사용·팀 의사소통은 알 수 없으므로, 연속 압박이나 장면의 의도는 판정하지 않습니다.",
]


def apply_analysis_semantics(analysis: dict[str, Any]) -> dict[str, Any]:
    """Assign evidence IDs, score groups, and build the statement layer."""
    _assign_evidence_ids(analysis)
    _assign_score_groups(analysis)
    analysis["statements"] = build_statements(analysis)
    return analysis


def _assign_evidence_ids(analysis: dict[str, Any]) -> None:
    match_id = analysis.get("match_id", "unknown")
    for index, item in enumerate(analysis.get("evidence", [])):
        item["id"] = evidence_id(match_id, item, index)


def evidence_id(match_id: str, item: dict[str, Any], index: int) -> str:
    return f"ev:{match_id}:{item.get('type') or 'unknown'}:{item.get('minute') or 0}:{index}"


def _assign_score_groups(analysis: dict[str, Any]) -> None:
    for metric_key, score in analysis.get("scores", {}).items():
        if not isinstance(score, dict):
            continue
        if metric_key in RISK_STYLE_METRICS:
            score["group"] = "risk_style"
        elif metric_key in PERFORMANCE_METRICS:
            score["group"] = "performance"
        else:
            # Unregistered metric: derive from direction so a future
            # higher_is_worse signal can never silently render as an
            # ability score (domain reviewer finding, 2026-07-13).
            score["group"] = (
                "risk_style" if score.get("direction") == "higher_is_worse" else "performance"
            )


def build_statements(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    statements: list[dict[str, Any]] = []
    evidence = analysis.get("evidence", [])

    for item in evidence:
        if _is_neutral(item):
            continue
        statements.append(
            _statement(
                kind="observation",
                text=f"{item.get('title')}: {item.get('description')}",
                evidence_ids=[item["id"]],
                confidence=item.get("confidence") or "medium",
            )
        )

    for text in STANDARD_LIMITATIONS:
        statements.append(_statement(kind="limitation", text=text, evidence_ids=[], confidence="high"))
    for metric_key, score in analysis.get("scores", {}).items():
        if not isinstance(score, dict):
            continue
        if score.get("value") is None:
            statements.append(
                _statement(
                    kind="limitation",
                    text=f"'{metric_key}'는 이 경기에서 산정되지 않았습니다(표본 또는 조건 부족).",
                    evidence_ids=[],
                    confidence="high",
                )
            )
        elif score.get("confidence") == "low":
            statements.append(
                _statement(
                    kind="limitation",
                    text=f"'{metric_key}' 점수는 데이터 해상도/표본 한계로 신뢰도가 낮습니다. 리플레이 확인 전에는 참고용으로만 보세요.",
                    evidence_ids=[],
                    confidence="high",
                )
            )

    statements.extend(_replay_questions(evidence))
    return statements


def _replay_questions(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    seen_minutes: set[int] = set()

    for item in evidence:
        if len(questions) >= MAX_REPLAY_QUESTIONS:
            break
        if _is_neutral(item) or item.get("type") not in REPLAY_WORTHY_KINDS:
            continue
        minute = int(item.get("minute") or 0)
        if minute <= 0 or minute in seen_minutes:
            continue
        seen_minutes.add(minute)
        questions.append(
            _statement(
                kind="replay_question",
                text=(
                    f"{minute}분 장면: 사망(또는 위험 노출) 20초 전 아군 위치, 미니맵에 노출된 상대 인원, "
                    "웨이브 상태를 리플레이에서 확인해 보세요."
                ),
                evidence_ids=[item["id"]],
                confidence="high",
            )
        )
    return questions


def _statement(kind: str, text: str, evidence_ids: list[str], confidence: str) -> dict[str, Any]:
    assert kind in STATEMENT_KINDS
    return {"kind": kind, "text": text, "evidence_ids": evidence_ids, "confidence": confidence}


def _is_neutral(item: dict[str, Any]) -> bool:
    """Mirrors evidence_contexts neutral detection: 'No ... detected' placeholders."""
    title = str(item.get("title") or "").lower()
    if title.startswith("no "):
        return True
    if int(item.get("minute") or 0) == 0 and ("no " in title or "not " in title):
        return True
    description = str(item.get("description") or "").lower()
    return "not enough" in description or "did not include" in description
