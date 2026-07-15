"""Persistence for moments and long-format metric scores."""

from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analysis import AnalysisReport, MetricScore, Moment
from app.models.match import MatchEvent, MatchParticipant, RiotMatch

MOMENT_WINDOW_MS = 15_000

# Remakes / abnormally short games distort per-game aggregates (SPEC §10.3
# exclusions). NULL durations (legacy rows) are kept.
MIN_VALID_GAME_DURATION_S = 300


def _not_a_remake():
    from sqlalchemy import or_

    return or_(
        RiotMatch.game_duration.is_(None),
        RiotMatch.game_duration >= MIN_VALID_GAME_DURATION_S,
    )

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


async def fetch_player_match_records(
    db: AsyncSession,
    puuid: str,
    limit: int = 20,
    queue_ids: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Load a player's recent stored matches as plain dicts for aggregation.

    Reads only the local DB (no Riot calls) — the ingest pipeline is what
    fills it. Each record: match metadata + participant stats + challenges +
    per-match metric values keyed by metric_key. Pass queue_ids to keep
    solo/flex/normal queues from being silently mixed (Phase 2 gap).
    """
    stmt = (
        select(MatchParticipant, RiotMatch.game_creation, RiotMatch.queue_id, RiotMatch.game_duration)
        .join(RiotMatch, RiotMatch.match_id == MatchParticipant.match_id)
        .where(MatchParticipant.puuid == puuid)
        .where(_not_a_remake())
        .order_by(RiotMatch.game_creation.desc().nulls_last())
        .limit(limit)
    )
    if queue_ids:
        stmt = stmt.where(RiotMatch.queue_id.in_(queue_ids))
    rows = (await db.execute(stmt)).all()

    records: list[dict[str, Any]] = []
    by_match: dict[str, dict[str, Any]] = {}
    for participant, game_creation, queue_id, game_duration in rows:
        raw = participant.raw_json or {}
        challenges = raw.get("challenges")
        record = {
            "match_id": participant.match_id,
            "game_creation": game_creation,
            "queue_id": queue_id,
            "game_duration": game_duration,
            "role": participant.team_position or participant.individual_position,
            "win": participant.win,
            "kills": participant.kills,
            "deaths": participant.deaths,
            "assists": participant.assists,
            "damage_to_champions": participant.damage_to_champions,
            "gold_earned": participant.gold_earned,
            "vision_score": participant.vision_score,
            "champion_name": participant.champion_name,
            "challenges": challenges if isinstance(challenges, dict) else {},
            "scores": {},
        }
        records.append(record)
        by_match[participant.match_id] = record

    if by_match:
        score_stmt = select(MetricScore).where(
            MetricScore.puuid == puuid,
            MetricScore.scope == "match",
            MetricScore.match_id.in_(list(by_match.keys())),
        )
        for score in (await db.execute(score_stmt)).scalars():
            record = by_match.get(score.match_id)
            if record is not None:
                record["scores"][score.metric_key] = score.value

    return records


async def fetch_player_event_history(
    db: AsyncSession,
    puuid: str,
    match_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Per-match combat context for pattern mining (M3).

    Returns {match_id: {participant_id, team_id, deaths[], kills[],
    enemy_objectives[]}} resolved against the player's participant id in each
    match. Reads only local tables filled by the ingest pipeline.
    """
    if not match_ids:
        return {}

    participants = (
        await db.execute(
            select(MatchParticipant).where(
                MatchParticipant.puuid == puuid,
                MatchParticipant.match_id.in_(match_ids),
            )
        )
    ).scalars()

    history: dict[str, dict[str, Any]] = {
        participant.match_id: {
            "participant_id": participant.participant_id,
            "team_id": participant.team_id,
            "deaths": [],
            "kills": [],
            "enemy_objectives": [],
            # All elite kills regardless of team — used to model objective
            # availability windows for the analyzable-death predicate.
            "elite_objectives": [],
        }
        for participant in participants
    }
    if not history:
        return {}

    events = (
        await db.execute(
            select(MatchEvent).where(
                MatchEvent.match_id.in_(list(history.keys())),
                MatchEvent.event_type.in_(["CHAMPION_KILL", "ELITE_MONSTER_KILL", "BUILDING_KILL"]),
            )
        )
    ).scalars()

    for event in events:
        context = history.get(event.match_id)
        if context is None:
            continue
        if event.event_type == "CHAMPION_KILL":
            raw = event.raw_json or {}
            point = {
                "timestamp_ms": event.timestamp_ms,
                "minute": event.minute,
                "x": event.position_x,
                "y": event.position_y,
                "shutdown_bounty": int(raw.get("shutdownBounty") or 0),
            }
            if event.victim_id == context["participant_id"]:
                context["deaths"].append(point)
            elif event.killer_id == context["participant_id"]:
                context["kills"].append(point)
            continue

        if event.event_type == "ELITE_MONSTER_KILL":
            context["elite_objectives"].append(
                {"timestamp_ms": event.timestamp_ms, "monster_type": event.monster_type}
            )

        objective_team = event.killer_team_id
        if event.event_type == "BUILDING_KILL":
            # BUILDING_KILL carries the *destroyed* team; credit the opponent.
            if event.team_id == 100:
                objective_team = 200
            elif event.team_id == 200:
                objective_team = 100
        if objective_team in (100, 200) and objective_team != context["team_id"]:
            context["enemy_objectives"].append(
                {
                    "timestamp_ms": event.timestamp_ms,
                    "minute": event.minute,
                    "event_type": event.event_type,
                    "monster_type": event.monster_type,
                    "building_type": event.building_type,
                }
            )

    for context in history.values():
        context["deaths"].sort(key=lambda item: item["timestamp_ms"])
        context["kills"].sort(key=lambda item: item["timestamp_ms"])
        context["enemy_objectives"].sort(key=lambda item: item["timestamp_ms"])
        context["elite_objectives"].sort(key=lambda item: item["timestamp_ms"])
    return history


async def get_cached_report(
    db: AsyncSession,
    puuid: str,
    cache_key: str,
    report_type: str = "summary",
) -> AnalysisReport | None:
    stmt = (
        select(AnalysisReport)
        .where(
            AnalysisReport.puuid == puuid,
            AnalysisReport.cache_key == cache_key,
            AnalysisReport.report_type == report_type,
        )
        .order_by(AnalysisReport.id.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalars().first()


async def save_report(
    db: AsyncSession,
    puuid: str,
    cache_key: str,
    window: str,
    generated_by: str,
    content: dict[str, Any],
    report_type: str = "summary",
) -> None:
    await db.execute(
        delete(AnalysisReport).where(
            AnalysisReport.puuid == puuid,
            AnalysisReport.cache_key == cache_key,
            AnalysisReport.report_type == report_type,
        )
    )
    db.add(
        AnalysisReport(
            puuid=puuid,
            report_type=report_type,
            window=window,
            cache_key=cache_key,
            generated_by=generated_by,
            content=content,
        )
    )
    await db.commit()


async def fetch_cohort_participant_stats(
    db: AsyncSession,
    role: str,
    queue_ids: list[int] | None = None,
    exclude_puuid: str | None = None,
    limit: int = 2000,
) -> list[dict[str, Any]]:
    """Local-sample cohort rows for percentile context (Phase 4).

    Every ingested match contributes ten role-tagged participants, so the
    local DB doubles as a small comparison population. Tier is NOT known for
    arbitrary participants — callers must label this cohort as a local sample,
    not a tier cohort.
    """
    stmt = (
        select(MatchParticipant, RiotMatch.game_duration)
        .join(RiotMatch, RiotMatch.match_id == MatchParticipant.match_id)
        .where(MatchParticipant.team_position == role)
        .where(_not_a_remake())
        .order_by(RiotMatch.game_creation.desc().nulls_last())
        .limit(limit)
    )
    if queue_ids:
        stmt = stmt.where(RiotMatch.queue_id.in_(queue_ids))
    if exclude_puuid:
        stmt = stmt.where(MatchParticipant.puuid != exclude_puuid)

    rows: list[dict[str, Any]] = []
    for participant, game_duration in (await db.execute(stmt)).all():
        raw = participant.raw_json or {}
        challenges = raw.get("challenges")
        rows.append(
            {
                "kills": participant.kills,
                "deaths": participant.deaths,
                "assists": participant.assists,
                "damage_to_champions": participant.damage_to_champions,
                "gold_earned": participant.gold_earned,
                "vision_score": participant.vision_score,
                "game_duration": game_duration,
                "challenges": challenges if isinstance(challenges, dict) else {},
            }
        )
    return rows


async def replace_aggregate_scores(
    db: AsyncSession,
    puuid: str,
    window: str,
    rows: list[dict[str, Any]],
    metric_version: int,
) -> None:
    """Replace scope=aggregate rows for (puuid, window) with freshly computed ones."""
    await db.execute(
        delete(MetricScore).where(
            MetricScore.puuid == puuid,
            MetricScore.scope == "aggregate",
            MetricScore.window == window,
        )
    )
    db.add_all(
        MetricScore(
            puuid=puuid,
            scope="aggregate",
            match_id=None,
            role=row.get("role"),
            window=window,
            metric_key=row["metric_key"],
            value=row.get("value"),
            confidence=row.get("confidence") or "medium",
            direction=row.get("direction") or "higher_is_better",
            evidence=row.get("evidence"),
            source="api",
            metric_version=metric_version,
        )
        for row in rows
    )
    await db.commit()
