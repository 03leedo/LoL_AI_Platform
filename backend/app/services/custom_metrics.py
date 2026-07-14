from typing import Any

# Bump when any score formula changes; stored scores carry this so raw JSON
# can be batch-recomputed and stale rows identified (master-plan §2).
# v2: habit metrics added (gold retention, gambler, teamfight persistence,
#     death acceleration).
METRIC_VERSION = 2

BLUE_TEAM_ID = 100
RED_TEAM_ID = 200
OBJECTIVE_WINDOW_MS = 90_000


class PlayerAnalysisError(Exception):
    pass


def analyze_player_match(
    match_id: str,
    puuid: str,
    match: dict[str, Any],
    timeline: dict[str, Any],
    features: list[dict[str, Any]],
) -> dict[str, Any]:
    participant = _participant_for_puuid(match, puuid)
    if participant is None:
        raise PlayerAnalysisError("Player was not found in this match")

    participant_id = int(participant["participantId"])
    team_id = int(participant["teamId"])
    events = _flatten_events(timeline)
    objective_events = [_objective_event(event, match) for event in events]
    objective_events = [event for event in objective_events if event is not None]
    death_events = [
        event
        for event in events
        if event.get("type") == "CHAMPION_KILL" and event.get("victimId") == participant_id
    ]

    death_cost, death_evidence = _death_cost_index(death_events, objective_events, features, team_id)
    throw_index, throw_evidence = _throw_index(death_events, objective_events, features, team_id)
    objective_setup, objective_evidence = _objective_setup_score(
        objective_events,
        events,
        team_id,
        participant_id,
    )
    lead_conversion, lead_evidence = _lead_conversion_score(
        objective_events,
        death_events,
        features,
        match,
        team_id,
    )
    stability_score = _clamp_score(round(100 - death_cost * 0.6 - throw_index * 0.4))

    evidence = death_evidence + throw_evidence + objective_evidence + lead_evidence
    evidence.sort(key=lambda item: (item["minute"], item["type"], item["title"]))

    return {
        "match_id": match_id,
        "player": {
            "puuid": puuid,
            "champion": participant.get("championName"),
            "role": participant.get("teamPosition") or participant.get("individualPosition"),
            "team": "blue" if team_id == BLUE_TEAM_ID else "red",
            "win": participant.get("win"),
        },
        "scores": {
            "death_cost_index": _score(death_cost, "medium", "higher_is_worse"),
            "throw_index": _score(throw_index, "medium", "higher_is_worse"),
            "objective_setup_score": _score(objective_setup, "medium", "higher_is_better"),
            "lead_conversion_score": _score(lead_conversion, "medium", "higher_is_better"),
            "stability_score": _score(stability_score, "medium", "higher_is_better"),
        },
        "evidence": evidence[:12],
    }


def _death_cost_index(
    death_events: list[dict[str, Any]],
    objective_events: list[dict[str, Any]],
    features: list[dict[str, Any]],
    team_id: int,
) -> tuple[int, list[dict[str, Any]]]:
    score = 0
    evidence: list[dict[str, Any]] = []

    for death in death_events:
        timestamp_ms = int(death.get("timestamp") or 0)
        minute = timestamp_ms // 60000
        enemy_objectives = _objective_events_after_death(objective_events, timestamp_ms, team_id)
        team_gold_diff = _team_gold_diff_at(features, timestamp_ms, team_id)
        death_score = 8

        for objective in enemy_objectives:
            death_score += _objective_weight(objective)
        if minute >= 20:
            death_score += 8
        if team_gold_diff > 1000:
            death_score += 8
        if int(death.get("shutdownBounty") or 0) > 0:
            death_score += 10

        score += death_score
        if enemy_objectives:
            objective_names = ", ".join(_objective_label(objective) for objective in enemy_objectives)
            evidence.append(
                _evidence(
                    minute=minute,
                    kind="death_cost",
                    title="Death was followed by objective loss",
                    description=(
                        f"Within 90 seconds of this death, the opposing team secured {objective_names}. "
                        "This is treated as a high-cost death rather than a simple death count."
                    ),
                )
            )
        elif minute >= 20 or team_gold_diff > 1000:
            evidence.append(
                _evidence(
                    minute=minute,
                    kind="death_cost",
                    title="Death carried elevated risk",
                    description=(
                        "This death happened after 20 minutes or while the team had a gold lead, "
                        "so the model treats it as more costly."
                    ),
                )
            )

    if not evidence:
        evidence.append(
            _evidence(
                minute=0,
                kind="death_cost",
                title="No high-cost death pattern detected",
                description="No player death was followed by a major objective loss in the 90 second review window.",
                confidence="medium",
            )
        )

    return _clamp_score(score), evidence


def _throw_index(
    death_events: list[dict[str, Any]],
    objective_events: list[dict[str, Any]],
    features: list[dict[str, Any]],
    team_id: int,
) -> tuple[int, list[dict[str, Any]]]:
    score = 0
    evidence: list[dict[str, Any]] = []

    for death in death_events:
        timestamp_ms = int(death.get("timestamp") or 0)
        before_diff = _team_gold_diff_at(features, timestamp_ms, team_id)
        after_diff = _team_gold_diff_at(features, timestamp_ms + OBJECTIVE_WINDOW_MS, team_id)
        enemy_objectives = _objective_events_after_death(objective_events, timestamp_ms, team_id)

        if before_diff <= 1000:
            continue

        swing = before_diff - after_diff
        death_score = 10
        if swing >= 1500:
            death_score += 20
        if after_diff < 0:
            death_score += 20
        if enemy_objectives:
            death_score += sum(_objective_weight(objective) // 2 for objective in enemy_objectives)

        score += death_score
        evidence.append(
            _evidence(
                minute=timestamp_ms // 60000,
                kind="throw_index",
                title="Lead was put at risk after death",
                description=(
                    f"The team was ahead by about {before_diff} gold before the death and "
                    f"the lead changed by about {swing} gold in the next 90 seconds."
                ),
            )
        )

    if not evidence:
        evidence.append(
            _evidence(
                minute=0,
                kind="throw_index",
                title="No clear throw pattern detected",
                description="The model did not find a death that clearly converted a team lead into a major loss.",
                confidence="medium",
            )
        )

    return _clamp_score(score), evidence


def _objective_setup_score(
    objective_events: list[dict[str, Any]],
    events: list[dict[str, Any]],
    team_id: int,
    participant_id: int,
) -> tuple[int, list[dict[str, Any]]]:
    score = 50
    evidence: list[dict[str, Any]] = []
    major_objectives = [event for event in objective_events if event["objective"] in {"dragon", "herald", "baron"}]

    if not major_objectives:
        return 50, [
            _evidence(
                minute=0,
                kind="objective_setup",
                title="No major objective event found",
                description="There was not enough objective event data to judge setup quality.",
                confidence="low",
            )
        ]

    for objective in major_objectives:
        timestamp_ms = int(objective["timestamp"])
        own_deaths_before = _team_deaths_in_window(events, team_id, timestamp_ms - OBJECTIVE_WINDOW_MS, timestamp_ms)
        won_objective = objective["team_id"] == team_id
        player_involved = objective.get("killer_id") == participant_id

        if won_objective and not own_deaths_before:
            score += 12
            title = "Objective setup converted cleanly"
            description = (
                f"The team secured {_objective_label(objective)} without an allied death in the 90 seconds before it."
            )
        elif won_objective:
            score += 5
            title = "Objective was secured with some setup risk"
            description = (
                f"The team secured {_objective_label(objective)}, but allied deaths before the objective lowered confidence."
            )
        else:
            score -= 10 + own_deaths_before * 4
            title = "Objective setup favored the opponent"
            description = (
                f"The opposing team secured {_objective_label(objective)} after {own_deaths_before} allied death(s) "
                "in the 90 second setup window."
            )

        if player_involved and won_objective:
            score += 5

        evidence.append(
            _evidence(
                minute=timestamp_ms // 60000,
                kind="objective_setup",
                title=title,
                description=description,
            )
        )

    return _clamp_score(score), evidence


def _lead_conversion_score(
    objective_events: list[dict[str, Any]],
    death_events: list[dict[str, Any]],
    features: list[dict[str, Any]],
    match: dict[str, Any],
    team_id: int,
) -> tuple[int | None, list[dict[str, Any]]]:
    lead_frame = _frame_at_minute(features, 15) or _frame_at_minute(features, 10)
    if not lead_frame:
        return None, [
            _evidence(
                minute=0,
                kind="lead_conversion",
                title="Lead conversion was not scored",
                description="The timeline did not include a usable 10 or 15 minute frame.",
                confidence="low",
            )
        ]

    lead_minute = int(lead_frame["minute"])
    lead = _team_gold_diff_from_frame(lead_frame, team_id)
    if lead <= 1000:
        return None, [
            _evidence(
                minute=lead_minute,
                kind="lead_conversion",
                title="No meaningful early lead detected",
                description="The team did not have enough of an early gold lead for lead conversion scoring.",
                confidence="medium",
            )
        ]

    score = 50
    evidence: list[dict[str, Any]] = []
    window_start = 15 * 60_000
    window_end = 25 * 60_000
    converted_objectives = [
        event
        for event in objective_events
        if event["team_id"] == team_id and window_start <= event["timestamp"] <= window_end
    ]
    risky_deaths = [
        death
        for death in death_events
        if window_start <= int(death.get("timestamp") or 0) <= window_end
    ]

    score += min(35, sum(_objective_weight(event) // 2 for event in converted_objectives))
    score -= min(30, len(risky_deaths) * 10)
    if _team_won(match, team_id):
        score += 10

    if converted_objectives:
        names = ", ".join(_objective_label(event) for event in converted_objectives)
        evidence.append(
            _evidence(
                minute=15,
                kind="lead_conversion",
                title="Early lead converted into objectives",
                description=f"The team had an early lead and converted it into {names} between 15 and 25 minutes.",
            )
        )
    if risky_deaths:
        evidence.append(
            _evidence(
                minute=int(risky_deaths[0].get("timestamp") or 0) // 60000,
                kind="lead_conversion",
                title="Deaths occurred during the lead conversion window",
                description="One or more player deaths occurred while the team was trying to convert an early lead.",
            )
        )
    if not evidence:
        evidence.append(
            _evidence(
                minute=lead_minute,
                kind="lead_conversion",
                title="Early lead had limited conversion evidence",
                description="An early lead was detected, but the 15 to 25 minute window had few objective conversions.",
            )
        )

    return _clamp_score(score), evidence


def _participant_for_puuid(match: dict[str, Any], puuid: str) -> dict[str, Any] | None:
    for participant in match.get("info", {}).get("participants", []):
        if participant.get("puuid") == puuid:
            return participant
    return None


def _flatten_events(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for frame in timeline.get("info", {}).get("frames", []):
        for event in frame.get("events", []):
            events.append(event)
    return events


def _objective_event(event: dict[str, Any], match: dict[str, Any]) -> dict[str, Any] | None:
    event_type = event.get("type")
    timestamp_ms = int(event.get("timestamp") or 0)

    if event_type == "BUILDING_KILL" and event.get("buildingType") == "TOWER_BUILDING":
        destroyed_team_id = event.get("teamId")
        team_id = _opponent_team_id(destroyed_team_id)
        if team_id is None:
            return None
        return {
            "timestamp": timestamp_ms,
            "team_id": team_id,
            "objective": "tower",
            "killer_id": event.get("killerId"),
        }

    if event_type != "ELITE_MONSTER_KILL":
        return None

    objective = _objective_key(event.get("monsterType"))
    if objective is None:
        return None

    team_id = event.get("killerTeamId")
    if team_id not in {BLUE_TEAM_ID, RED_TEAM_ID}:
        team_id = _team_for_participant(match, int(event.get("killerId") or 0))
    if team_id not in {BLUE_TEAM_ID, RED_TEAM_ID}:
        return None

    return {
        "timestamp": timestamp_ms,
        "team_id": int(team_id),
        "objective": objective,
        "killer_id": event.get("killerId"),
    }


def _objective_events_after_death(
    objective_events: list[dict[str, Any]],
    death_timestamp_ms: int,
    team_id: int,
) -> list[dict[str, Any]]:
    return [
        event
        for event in objective_events
        if event["team_id"] != team_id
        and death_timestamp_ms <= event["timestamp"] <= death_timestamp_ms + OBJECTIVE_WINDOW_MS
    ]


def _team_deaths_in_window(
    events: list[dict[str, Any]],
    team_id: int,
    start_ms: int,
    end_ms: int,
) -> int:
    count = 0
    for event in events:
        if event.get("type") != "CHAMPION_KILL":
            continue
        timestamp_ms = int(event.get("timestamp") or 0)
        if not start_ms <= timestamp_ms <= end_ms:
            continue
        victim_id = int(event.get("victimId") or 0)
        victim_team_id = _fallback_team_id(victim_id)
        if victim_team_id == team_id:
            count += 1
    return count


def _team_gold_diff_at(features: list[dict[str, Any]], timestamp_ms: int, team_id: int) -> int:
    if not features:
        return 0
    frame = min(features, key=lambda item: abs(int(item["timestamp_ms"]) - timestamp_ms))
    return _team_gold_diff_from_frame(frame, team_id)


def _team_gold_diff_from_frame(frame: dict[str, Any], team_id: int) -> int:
    gold_diff = int(frame.get("gold_diff") or 0)
    return gold_diff if team_id == BLUE_TEAM_ID else -gold_diff


def _frame_at_minute(features: list[dict[str, Any]], minute: int) -> dict[str, Any] | None:
    if not features:
        return None
    return min(features, key=lambda item: abs(int(item["minute"]) - minute))


def _team_for_participant(match: dict[str, Any], participant_id: int) -> int | None:
    for participant in match.get("info", {}).get("participants", []):
        if participant.get("participantId") == participant_id:
            return participant.get("teamId")
    if participant_id:
        return _fallback_team_id(participant_id)
    return None


def _team_won(match: dict[str, Any], team_id: int) -> bool:
    for team in match.get("info", {}).get("teams", []):
        if team.get("teamId") == team_id:
            return bool(team.get("win"))
    for participant in match.get("info", {}).get("participants", []):
        if participant.get("teamId") == team_id:
            return bool(participant.get("win"))
    return False


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


def _objective_weight(objective: dict[str, Any]) -> int:
    weights = {"baron": 25, "dragon": 16, "herald": 14, "tower": 10}
    return weights.get(objective["objective"], 8)


def _objective_label(objective: dict[str, Any]) -> str:
    labels = {"baron": "Baron", "dragon": "Dragon", "herald": "Rift Herald", "tower": "Tower"}
    return labels.get(objective["objective"], "objective")


def _score(value: int | None, confidence: str, direction: str) -> dict[str, Any]:
    return {
        "value": value,
        "confidence": confidence,
        "direction": direction,
    }


def _evidence(
    minute: int,
    kind: str,
    title: str,
    description: str,
    confidence: str = "medium",
) -> dict[str, Any]:
    return {
        "minute": minute,
        "type": kind,
        "title": title,
        "description": description,
        "confidence": confidence,
    }


def _clamp_score(value: int) -> int:
    return max(0, min(100, value))
