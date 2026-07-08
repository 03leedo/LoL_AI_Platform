"""Kill/death heatmap aggregation over recent matches (master-plan §4.4).

Positions come straight from timeline CHAMPION_KILL events, so no extra data
source is needed. Zone labels are coarse geometric approximations on the
0..15000 Summoner's Rift coordinate space; they exist to make the "death zone"
callout readable, not to be pixel-accurate.
"""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.matches import replace_match_events
from app.services.match_data import get_match_cached, get_timeline_cached
from app.services.riot_client import RiotApiError, RiotClient

logger = logging.getLogger(__name__)

BLUE_TEAM_ID = 100
MAP_DIAGONAL_SUM = 15_000
LANE_EDGE = 3000
LANE_FAR_EDGE = 12_000
MID_BAND = 2000

ZONE_TOP = "top"
ZONE_MID = "mid"
ZONE_BOT = "bot"
ZONE_ALLY_JUNGLE = "ally_jungle"
ZONE_ENEMY_JUNGLE = "enemy_jungle"

DEATH_ZONE_MIN_COUNT = 4
DEATH_ZONE_MIN_SHARE = 0.30


def zone_of(x: int, y: int, team_id: int) -> str:
    """Classify a map coordinate into a coarse named zone from one team's view."""
    if abs(x - y) < MID_BAND and 2500 < x < 12_500:
        return ZONE_MID
    if (x < LANE_EDGE and y > LANE_EDGE) or (y > LANE_FAR_EDGE and x < LANE_FAR_EDGE):
        return ZONE_TOP
    if (y < LANE_EDGE and x > LANE_EDGE) or (x > LANE_FAR_EDGE and y < LANE_FAR_EDGE):
        return ZONE_BOT

    on_blue_half = (x + y) < MAP_DIAGONAL_SUM
    if team_id == BLUE_TEAM_ID:
        return ZONE_ALLY_JUNGLE if on_blue_half else ZONE_ENEMY_JUNGLE
    return ZONE_ENEMY_JUNGLE if on_blue_half else ZONE_ALLY_JUNGLE


async def build_summoner_heatmap(
    db: AsyncSession,
    client: RiotClient,
    puuid: str,
    match_ids: list[str],
    platform_routing: str,
) -> dict[str, Any]:
    kills: list[dict[str, Any]] = []
    deaths: list[dict[str, Any]] = []
    analyzed = 0

    for match_id in match_ids:
        try:
            match, _ = await get_match_cached(db, client, match_id, platform_routing)
            timeline, timeline_cached = await get_timeline_cached(db, client, match_id)
        except RiotApiError as exc:
            logger.warning("Heatmap skipped match %s: %s", match_id, exc.message)
            continue

        participant = _participant_for_puuid(match, puuid)
        if participant is None:
            continue
        participant_id = int(participant.get("participantId") or 0)
        team_id = int(participant.get("teamId") or 0)
        side = "blue" if team_id == BLUE_TEAM_ID else "red"

        if not timeline_cached:
            try:
                await replace_match_events(db=db, match_id=match_id, timeline=timeline)
                await db.commit()
            except Exception as exc:  # pragma: no cover - heatmap must survive persistence drift
                logger.warning("Heatmap event persistence skipped for %s: %s", match_id, exc)
                try:
                    await db.rollback()
                except Exception:  # pragma: no cover
                    pass

        for event in _kill_events(timeline):
            position = event.get("position") or {}
            x, y = position.get("x"), position.get("y")
            if x is None or y is None:
                continue
            point = {
                "match_id": match_id,
                "minute": int(event.get("timestamp") or 0) // 60_000,
                "x": int(x),
                "y": int(y),
                "side": side,
                "zone": zone_of(int(x), int(y), team_id),
            }
            if event.get("killerId") == participant_id:
                kills.append(point)
            elif event.get("victimId") == participant_id:
                deaths.append(point)

        analyzed += 1

    return {
        "puuid": puuid,
        "matches_requested": len(match_ids),
        "matches_analyzed": analyzed,
        "kills": kills,
        "deaths": deaths,
        "kill_zones": _zone_stats(kills),
        "death_zones": _zone_stats(deaths, flag_death_zone=True),
    }


def _zone_stats(points: list[dict[str, Any]], flag_death_zone: bool = False) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for point in points:
        counts[point["zone"]] = counts.get(point["zone"], 0) + 1

    total = len(points)
    stats = [
        {
            "zone": zone,
            "count": count,
            "share": round(count / total, 2) if total else 0.0,
        }
        for zone, count in counts.items()
    ]
    stats.sort(key=lambda item: (-item["count"], item["zone"]))

    if flag_death_zone:
        for stat in stats:
            stat["is_death_zone"] = (
                stat["count"] >= DEATH_ZONE_MIN_COUNT and stat["share"] >= DEATH_ZONE_MIN_SHARE
            )
    return stats


def _kill_events(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for frame in timeline.get("info", {}).get("frames", []):
        for event in frame.get("events", []):
            if event.get("type") == "CHAMPION_KILL":
                events.append(event)
    return events


def _participant_for_puuid(match: dict[str, Any], puuid: str) -> dict[str, Any] | None:
    for participant in match.get("info", {}).get("participants", []):
        if participant.get("puuid") == puuid:
            return participant
    return None
