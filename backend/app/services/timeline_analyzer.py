from typing import Any

BLUE_TEAM_ID = 100
RED_TEAM_ID = 200


def analyze_match_timeline(
    match_id: str,
    match: dict[str, Any],
    timeline: dict[str, Any],
) -> list[dict[str, Any]]:
    participant_teams = _participant_teams(match)
    counters = _empty_objective_counters()
    analyzed_frames: list[dict[str, Any]] = []

    frames = timeline.get("info", {}).get("frames", [])
    for frame in frames:
        _apply_objective_events(frame.get("events", []), participant_teams, counters)
        totals = _team_totals(frame.get("participantFrames", {}), participant_teams)

        timestamp_ms = int(frame.get("timestamp") or 0)
        analyzed_frames.append(
            {
                "match_id": match_id,
                "minute": timestamp_ms // 60000,
                "timestamp_ms": timestamp_ms,
                "blue_gold": totals[BLUE_TEAM_ID]["gold"],
                "red_gold": totals[RED_TEAM_ID]["gold"],
                "gold_diff": totals[BLUE_TEAM_ID]["gold"] - totals[RED_TEAM_ID]["gold"],
                "blue_xp": totals[BLUE_TEAM_ID]["xp"],
                "red_xp": totals[RED_TEAM_ID]["xp"],
                "xp_diff": totals[BLUE_TEAM_ID]["xp"] - totals[RED_TEAM_ID]["xp"],
                "blue_cs": totals[BLUE_TEAM_ID]["cs"],
                "red_cs": totals[RED_TEAM_ID]["cs"],
                "cs_diff": totals[BLUE_TEAM_ID]["cs"] - totals[RED_TEAM_ID]["cs"],
                "blue_tower_kills": counters[BLUE_TEAM_ID]["tower"],
                "red_tower_kills": counters[RED_TEAM_ID]["tower"],
                "blue_dragon_kills": counters[BLUE_TEAM_ID]["dragon"],
                "red_dragon_kills": counters[RED_TEAM_ID]["dragon"],
                "blue_herald_kills": counters[BLUE_TEAM_ID]["herald"],
                "red_herald_kills": counters[RED_TEAM_ID]["herald"],
                "blue_baron_kills": counters[BLUE_TEAM_ID]["baron"],
                "red_baron_kills": counters[RED_TEAM_ID]["baron"],
                "raw_frame": frame,
            }
        )

    return analyzed_frames


def _participant_teams(match: dict[str, Any]) -> dict[int, int]:
    teams: dict[int, int] = {}
    for participant in match.get("info", {}).get("participants", []):
        participant_id = participant.get("participantId")
        team_id = participant.get("teamId")
        if participant_id in {None, 0} or team_id not in {BLUE_TEAM_ID, RED_TEAM_ID}:
            continue
        teams[int(participant_id)] = int(team_id)
    return teams


def _empty_objective_counters() -> dict[int, dict[str, int]]:
    return {
        BLUE_TEAM_ID: {"tower": 0, "dragon": 0, "herald": 0, "baron": 0},
        RED_TEAM_ID: {"tower": 0, "dragon": 0, "herald": 0, "baron": 0},
    }


def _team_totals(
    participant_frames: dict[str, dict[str, Any]],
    participant_teams: dict[int, int],
) -> dict[int, dict[str, int]]:
    totals = {
        BLUE_TEAM_ID: {"gold": 0, "xp": 0, "cs": 0},
        RED_TEAM_ID: {"gold": 0, "xp": 0, "cs": 0},
    }

    for fallback_id, participant_frame in participant_frames.items():
        participant_id = int(participant_frame.get("participantId") or fallback_id)
        team_id = participant_teams.get(participant_id, _fallback_team_id(participant_id))
        totals[team_id]["gold"] += int(participant_frame.get("totalGold") or 0)
        totals[team_id]["xp"] += int(participant_frame.get("xp") or 0)
        totals[team_id]["cs"] += int(participant_frame.get("minionsKilled") or 0)
        totals[team_id]["cs"] += int(participant_frame.get("jungleMinionsKilled") or 0)

    return totals


def _apply_objective_events(
    events: list[dict[str, Any]],
    participant_teams: dict[int, int],
    counters: dict[int, dict[str, int]],
) -> None:
    for event in events:
        event_type = event.get("type")

        if event_type == "BUILDING_KILL" and event.get("buildingType") == "TOWER_BUILDING":
            destroyed_team_id = event.get("teamId")
            scoring_team_id = _opponent_team_id(destroyed_team_id)
            if scoring_team_id:
                counters[scoring_team_id]["tower"] += 1

        if event_type != "ELITE_MONSTER_KILL":
            continue

        objective = _objective_key(event.get("monsterType"))
        if not objective:
            continue

        scoring_team_id = event.get("killerTeamId")
        if scoring_team_id not in {BLUE_TEAM_ID, RED_TEAM_ID}:
            scoring_team_id = participant_teams.get(int(event.get("killerId") or 0))
        if scoring_team_id in {BLUE_TEAM_ID, RED_TEAM_ID}:
            counters[int(scoring_team_id)][objective] += 1


def _fallback_team_id(participant_id: int) -> int:
    return BLUE_TEAM_ID if participant_id <= 5 else RED_TEAM_ID


def _opponent_team_id(team_id: int | None) -> int | None:
    if team_id == BLUE_TEAM_ID:
        return RED_TEAM_ID
    if team_id == RED_TEAM_ID:
        return BLUE_TEAM_ID
    return None


def _objective_key(monster_type: str | None) -> str | None:
    if monster_type == "DRAGON":
        return "dragon"
    if monster_type == "RIFTHERALD":
        return "herald"
    if monster_type == "BARON_NASHOR":
        return "baron"
    return None
