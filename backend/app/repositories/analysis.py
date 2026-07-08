"""Persistence for moments and long-format metric scores."""

from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import MetricScore, Moment

MOMENT_WINDOW_MS = 15_000

ELITE_MOMENT_TYPES = {"dragon", "herald", "baron", "voidgrub", "atakhan"}

# Maps metric keys to the evidence `type` emitted by custom_metrics / habit_metrics.
METRIC_EVIDENCE_TYPES: dict[str, str | None] = {
    "death_cost_index": "death_cost",
    "throw_index": "throw_index",
    "objective_setup_score": "objective_setup",
    "lead_conversion_score": "lead_conversion",
    "stability_score": None,
    "gold_retention_score": "gold_retention",
    "gambler_index": "gambler",
    "teamfight_persistence_score": "teamfight",
    "death_acceleration_index": "death_chain",
}


def _moment_importance(event: dict[str, Any]) -> int:
    participants = event.get("participants") or []
    if any(p.get("is_player") and p.get("is_actor") for p in participants):
        return 3
    if event.get("type") in ELITE_MOMENT_TYPES:
        return 2
    if any(p.get("is_player") for p in participants):
        return 2
    return 1


def build_moments(
    match_id: str,
    puuid: str,
    key_events: list[dict[str, Any]],
    source: str = "api",
) -> list[Moment]:
    moments: list[Moment] = []
    for event in key_events:
        timestamp_ms = int(event.get("timestamp_ms") or 0)
        moments.append(
            Moment(
                match_id=match_id,
                puuid=puuid,
                t_start_ms=max(0, timestamp_ms - MOMENT_WINDOW_MS),
                t_end_ms=timestamp_ms + MOMENT_WINDOW_MS,
                moment_type=str(event.get("type") or "unknown"),
                importance=_moment_importance(event),
                source=source,
                evidence=event,
            )
        )
    return moments


async def replace_match_moments(
    db: AsyncSession,
    match_id: str,
    puuid: str,
    key_events: list[dict[str, Any]],
) -> None:
    await db.execute(
        delete(Moment).where(Moment.match_id == match_id, Moment.puuid == puuid)
    )
    db.add_all(build_moments(match_id=match_id, puuid=puuid, key_events=key_events))
    await db.commit()


def build_metric_scores(analysis: dict[str, Any], metric_version: int) -> list[MetricScore]:
    match_id = analysis["match_id"]
    player = analysis.get("player", {})
    puuid = player["puuid"]

    evidence_by_type: dict[str, list[dict[str, Any]]] = {}
    for item in analysis.get("evidence", []):
        evidence_by_type.setdefault(str(item.get("type") or ""), []).append(item)

    rows: list[MetricScore] = []
    for metric_key, score in analysis.get("scores", {}).items():
        evidence_type = METRIC_EVIDENCE_TYPES.get(metric_key)
        evidence_items = evidence_by_type.get(evidence_type, []) if evidence_type else []
        rows.append(
            MetricScore(
                puuid=puuid,
                scope="match",
                match_id=match_id,
                role=player.get("role"),
                metric_key=metric_key,
                value=score.get("value"),
                confidence=score.get("confidence") or "medium",
                direction=score.get("direction") or "higher_is_better",
                evidence={"items": evidence_items} if evidence_items else None,
                source="api",
                metric_version=metric_version,
            )
        )
    return rows


async def replace_match_metric_scores(
    db: AsyncSession,
    analysis: dict[str, Any],
    metric_version: int,
) -> None:
    match_id = analysis["match_id"]
    puuid = analysis["player"]["puuid"]
    await db.execute(
        delete(MetricScore).where(
            MetricScore.match_id == match_id,
            MetricScore.puuid == puuid,
            MetricScore.scope == "match",
        )
    )
    db.add_all(build_metric_scores(analysis=analysis, metric_version=metric_version))
    await db.commit()
