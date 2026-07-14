"""Habit metrics: play-pattern scores layered on top of the core custom metrics.

Implements master-plan §4.1-4.3 and §4.5:
- gold_retention_score       (higher is worse)  unspent-gold snowball delay
- gambler_index              (higher is worse)  risk appetite: shutdowns conceded,
                                                isolated deaths, deep aggression
- teamfight_persistence_score (higher is better) staying alive and dealing damage
                                                through detected teamfights
- death_acceleration_index   (higher is worse)  chained deaths after a first fall

All scores follow the shared contract: {value, confidence, direction} plus
evidence items. Frame data is minute-granular, so position/gold judgements are
approximations and confidence is capped accordingly (master-plan §3.2).
"""

import math
from typing import Any

from app.services.challenges import get_challenge_int

BLUE_TEAM_ID = 100
RED_TEAM_ID = 200

RICH_GOLD_THRESHOLD = 1500
WALLET_DEATH_THRESHOLD = 1300
ENDGAME_EXCLUDED_MINUTES = 2

ISOLATION_DISTANCE = 4000
MAP_DIAGONAL_SUM = 15_000
DEEP_TERRITORY_MARGIN = 1000

FIGHT_GAP_MS = 20_000
FIGHT_MIN_KILLS = 3
FIGHT_MIN_PARTICIPANTS = 4
FIGHT_EDGE_PADDING_MS = 5_000

DEATH_CHAIN_WINDOW_MS = 300_000

MERGED_EVIDENCE_LIMIT = 16


def merge_habit_metrics(
    analysis: dict[str, Any],
    match: dict[str, Any],
    timeline: dict[str, Any],
    features: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute habit metrics and fold them into an analyze_player_match result."""
    puuid = analysis.get("player", {}).get("puuid")
    participant = _participant_for_puuid(match, puuid)
    if participant is None:
        return analysis

    participant_id = int(participant.get("participantId") or 0)
    team_id = int(participant.get("teamId") or 0)
    events = _flatten_events(timeline)
    my_deaths = [
        event
        for event in events
        if event.get("type") == "CHAMPION_KILL" and _optional_int(event.get("victimId")) == participant_id
    ]
    my_kills = [
        event
        for event in events
        if event.get("type") == "CHAMPION_KILL" and _optional_int(event.get("killerId")) == participant_id
    ]

    gold_retention, gold_evidence = _gold_retention(participant_id, my_deaths, features)
    gambler, gambler_evidence = _gambler_index(participant_id, team_id, my_deaths, my_kills, features)
    teamfight, teamfight_evidence = _teamfight_persistence(
        participant_id, team_id, match, events, features, participant
    )
    death_chain, chain_evidence = _death_acceleration(my_deaths)

    analysis["scores"].update(
        {
            "gold_retention_score": gold_retention,
            "gambler_index": gambler,
            "teamfight_persistence_score": teamfight,
            "death_acceleration_index": death_chain,
        }
    )

    merged_evidence = (
        list(analysis.get("evidence", []))
        + gold_evidence
        + gambler_evidence
        + teamfight_evidence
        + chain_evidence
    )
    merged_evidence.sort(key=lambda item: (item["minute"], item["type"], item["title"]))
    analysis["evidence"] = merged_evidence[:MERGED_EVIDENCE_LIMIT]
    return analysis


# ---------------------------------------------------------------------------
# 4.1 Gold retention


def _gold_retention(
    participant_id: int,
    my_deaths: list[dict[str, Any]],
    features: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    gold_by_minute = _current_gold_by_minute(participant_id, features)
    if not gold_by_minute:
        return _score(None, "low", "higher_is_worse"), [
            _evidence(
                minute=0,
                kind="gold_retention",
                title="Gold retention was not scored",
                description="The timeline did not include per-participant gold data.",
                confidence="low",
            )
        ]

    last_minute = max(minute for minute, _ in gold_by_minute)
    usable = [
        (minute, gold)
        for minute, gold in gold_by_minute
        if 2 <= minute <= last_minute - ENDGAME_EXCLUDED_MINUTES
    ]

    score = 0
    evidence: list[dict[str, Any]] = []

    for start, end, peak_gold in _rich_streaks(usable):
        length = end - start + 1
        if length < 2:
            continue
        score += 7 * length
        if len(evidence) < 3:
            evidence.append(
                _evidence(
                    minute=start,
                    kind="gold_retention",
                    title="Gold stayed unspent on the map",
                    description=(
                        f"Between minute {start} and {end} the player held {RICH_GOLD_THRESHOLD}+ gold "
                        f"(peaking around {peak_gold}) without converting it into items. "
                        "Item conversion was delayed through this stretch."
                    ),
                )
            )

    for death in my_deaths:
        timestamp_ms = int(death.get("timestamp") or 0)
        gold_at_death = _gold_near_timestamp(gold_by_minute, timestamp_ms)
        if gold_at_death is not None and gold_at_death >= WALLET_DEATH_THRESHOLD:
            score += 12
            evidence.append(
                _evidence(
                    minute=timestamp_ms // 60_000,
                    kind="gold_retention",
                    title="Died carrying a full wallet",
                    description=(
                        f"About {gold_at_death} gold was still unspent at the time of this death "
                        "(nearest minute frame)."
                    ),
                )
            )

    if not evidence:
        evidence.append(
            _evidence(
                minute=0,
                kind="gold_retention",
                title="No gold hoarding pattern detected",
                description="The player converted gold into items at a healthy tempo in this match.",
            )
        )

    return _score(_clamp(score), "medium", "higher_is_worse"), evidence


def _current_gold_by_minute(
    participant_id: int,
    features: list[dict[str, Any]],
) -> list[tuple[int, int]]:
    key = str(participant_id)
    result: list[tuple[int, int]] = []
    for feature in features:
        frame = feature.get("raw_frame") or {}
        participant_frames = frame.get("participantFrames") or {}
        participant_frame = participant_frames.get(key)
        if not isinstance(participant_frame, dict):
            continue
        current_gold = participant_frame.get("currentGold")
        if current_gold is None:
            continue
        result.append((int(feature.get("minute") or 0), int(current_gold)))
    result.sort(key=lambda item: item[0])
    return result


def _rich_streaks(gold_by_minute: list[tuple[int, int]]) -> list[tuple[int, int, int]]:
    streaks: list[tuple[int, int, int]] = []
    start: int | None = None
    prev_minute: int | None = None
    peak = 0

    for minute, gold in gold_by_minute:
        if gold >= RICH_GOLD_THRESHOLD and (prev_minute is None or start is None or minute == prev_minute + 1):
            if start is None:
                start = minute
                peak = gold
            peak = max(peak, gold)
        elif gold >= RICH_GOLD_THRESHOLD:
            if start is not None and prev_minute is not None:
                streaks.append((start, prev_minute, peak))
            start = minute
            peak = gold
        else:
            if start is not None and prev_minute is not None:
                streaks.append((start, prev_minute, peak))
            start = None
            peak = 0
        prev_minute = minute

    if start is not None and prev_minute is not None:
        streaks.append((start, prev_minute, peak))
    return streaks


def _gold_near_timestamp(gold_by_minute: list[tuple[int, int]], timestamp_ms: int) -> int | None:
    if not gold_by_minute:
        return None
    minute = timestamp_ms / 60_000
    nearest = min(gold_by_minute, key=lambda item: abs(item[0] - minute))
    return nearest[1]


# ---------------------------------------------------------------------------
# 4.2 Gambler index


def _gambler_index(
    participant_id: int,
    team_id: int,
    my_deaths: list[dict[str, Any]],
    my_kills: list[dict[str, Any]],
    features: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    score = 0
    evidence: list[dict[str, Any]] = []
    deep_deaths = 0

    for death in my_deaths:
        timestamp_ms = int(death.get("timestamp") or 0)
        minute = timestamp_ms // 60_000

        shutdown = int(death.get("shutdownBounty") or 0)
        if shutdown > 0:
            score += min(20, 10 + shutdown // 100)
            evidence.append(
                _evidence(
                    minute=minute,
                    kind="gambler",
                    title="Shutdown gold was conceded",
                    description=(
                        f"This death handed the enemy about {shutdown} bonus shutdown gold."
                    ),
                )
            )

        position = death.get("position") or {}
        x, y = _optional_int(position.get("x")), _optional_int(position.get("y"))

        nearest_ally_distance = _nearest_ally_distance(
            participant_id, team_id, x, y, timestamp_ms, features
        )
        if nearest_ally_distance is not None and nearest_ally_distance >= ISOLATION_DISTANCE:
            score += 12
            evidence.append(
                _evidence(
                    minute=minute,
                    kind="gambler",
                    title="Isolated death away from allies",
                    description=(
                        f"At the nearest minute frame the closest ally was about "
                        f"{int(nearest_ally_distance)} units away when this death happened "
                        "(frame-based estimate, +-30s)."
                    ),
                )
            )

        if x is not None and y is not None and _in_enemy_half(x, y, team_id, DEEP_TERRITORY_MARGIN):
            score += 6
            deep_deaths += 1

    deep_kills = sum(
        1
        for kill in my_kills
        if _event_in_enemy_half(kill, team_id, DEEP_TERRITORY_MARGIN)
    )
    if deep_kills:
        score += min(20, 4 * deep_kills)
        evidence.append(
            _evidence(
                minute=int(my_kills[0].get("timestamp") or 0) // 60_000,
                kind="gambler",
                title="Aggressive kills deep in enemy territory",
                description=(
                    f"{deep_kills} kill(s) happened deep inside the enemy half."
                ),
            )
        )
    if deep_deaths:
        evidence.append(
            _evidence(
                minute=0 if not my_deaths else int(my_deaths[0].get("timestamp") or 0) // 60_000,
                kind="gambler",
                title="Deaths occurred deep in enemy territory",
                description=(
                    f"{deep_deaths} death(s) happened well past the map midline, "
                    "where escape routes and ally cover are thinnest."
                ),
            )
        )

    if not evidence:
        evidence.append(
            _evidence(
                minute=0,
                kind="gambler",
                title="No high-risk play pattern detected",
                description="No shutdown concessions, isolated deaths, or deep-territory trades stood out.",
            )
        )

    return _score(_clamp(score), "medium", "higher_is_worse"), evidence


def _nearest_ally_distance(
    participant_id: int,
    team_id: int,
    x: int | None,
    y: int | None,
    timestamp_ms: int,
    features: list[dict[str, Any]],
) -> float | None:
    if x is None or y is None or not features:
        return None

    frame = min(features, key=lambda item: abs(int(item.get("timestamp_ms") or 0) - timestamp_ms))
    participant_frames = (frame.get("raw_frame") or {}).get("participantFrames") or {}

    ally_ids = _team_participant_ids(team_id)
    distances: list[float] = []
    for ally_id in ally_ids:
        if ally_id == participant_id:
            continue
        ally_frame = participant_frames.get(str(ally_id))
        if not isinstance(ally_frame, dict):
            continue
        position = ally_frame.get("position") or {}
        ax, ay = _optional_int(position.get("x")), _optional_int(position.get("y"))
        if ax is None or ay is None:
            continue
        distances.append(math.hypot(ax - x, ay - y))

    if not distances:
        return None
    return min(distances)


def _team_participant_ids(team_id: int) -> list[int]:
    return [1, 2, 3, 4, 5] if team_id == BLUE_TEAM_ID else [6, 7, 8, 9, 10]


def _event_in_enemy_half(event: dict[str, Any], team_id: int, margin: int) -> bool:
    position = event.get("position") or {}
    x, y = _optional_int(position.get("x")), _optional_int(position.get("y"))
    if x is None or y is None:
        return False
    return _in_enemy_half(x, y, team_id, margin)


def _in_enemy_half(x: int, y: int, team_id: int, margin: int = 0) -> bool:
    diagonal = x + y
    if team_id == BLUE_TEAM_ID:
        return diagonal > MAP_DIAGONAL_SUM + margin
    return diagonal < MAP_DIAGONAL_SUM - margin


# ---------------------------------------------------------------------------
# 4.3 Teamfight persistence


def _teamfight_persistence(
    participant_id: int,
    team_id: int,
    match: dict[str, Any],
    events: list[dict[str, Any]],
    features: list[dict[str, Any]],
    participant: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fights = _detect_teamfights(events)
    if not fights:
        return _score(None, "low", "higher_is_better"), [
            _evidence(
                minute=0,
                kind="teamfight",
                title="No teamfight window detected",
                description="Not enough clustered kills were found to score teamfight persistence.",
                confidence="low",
            )
        ]

    team_ids = _team_ids_by_participant(match)
    score = 50
    involved_fights = 0
    evidence: list[dict[str, Any]] = []

    for fight in fights:
        start_ms, end_ms, kills = fight
        fight_participants = _fight_participant_ids(kills)
        damage_share = _damage_share_in_window(
            participant_id, team_id, team_ids, start_ms, end_ms, features
        )
        involved = participant_id in fight_participants or (damage_share or 0) > 0.05
        if not involved:
            continue

        involved_fights += 1
        died = any(
            _optional_int(kill.get("victimId")) == participant_id
            and start_ms - FIGHT_EDGE_PADDING_MS <= int(kill.get("timestamp") or 0) <= end_ms + FIGHT_EDGE_PADDING_MS
            for kill in kills
        )

        if died:
            score -= 6
        else:
            score += 8
        if damage_share is not None:
            if damage_share >= 0.28:
                score += 8
            elif damage_share >= 0.20:
                score += 4

        if len(evidence) < 4:
            minute = start_ms // 60_000
            share_text = (
                f"about {round(damage_share * 100)}% of the team's damage in that window"
                if damage_share is not None
                else "an unknown share of team damage (frame data missing)"
            )
            evidence.append(
                _evidence(
                    minute=minute,
                    kind="teamfight",
                    title=(
                        "Held presence through a teamfight" if not died else "Fell during a teamfight"
                    ),
                    description=(
                        f"A {len(kills)}-kill fight broke out around minute {minute}; the player "
                        f"{'survived it' if not died else 'died in it'} while dealing {share_text}."
                    ),
                    confidence="low",
                )
            )

    if involved_fights == 0:
        return _score(None, "low", "higher_is_better"), [
            _evidence(
                minute=fights[0][0] // 60_000,
                kind="teamfight",
                title="No participation in detected teamfights",
                description="Teamfights happened, but the player was not detected in any of them.",
                confidence="low",
            )
        ]

    clutch_survivals = get_challenge_int(participant, "survivedSingleDigitHpCount")
    if clutch_survivals > 0:
        score += min(6, clutch_survivals * 2)
        evidence.append(
            _evidence(
                minute=0 if not fights else fights[0][0] // 60_000,
                kind="teamfight",
                title="Survived on single-digit HP",
                description=(
                    f"Riot's challenge stats record {clutch_survivals} fight(s) survived at single-digit HP - "
                    "a strong signal of limit-testing survivability."
                ),
                confidence="high",
            )
        )

    confidence = "medium" if involved_fights >= 2 else "low"
    return _score(_clamp(score), confidence, "higher_is_better"), evidence


def _detect_teamfights(events: list[dict[str, Any]]) -> list[tuple[int, int, list[dict[str, Any]]]]:
    kills = sorted(
        (event for event in events if event.get("type") == "CHAMPION_KILL"),
        key=lambda event: int(event.get("timestamp") or 0),
    )

    fights: list[tuple[int, int, list[dict[str, Any]]]] = []
    cluster: list[dict[str, Any]] = []

    for kill in kills:
        timestamp = int(kill.get("timestamp") or 0)
        if cluster and timestamp - int(cluster[-1].get("timestamp") or 0) > FIGHT_GAP_MS:
            _append_fight(fights, cluster)
            cluster = []
        cluster.append(kill)
    _append_fight(fights, cluster)
    return fights


def _append_fight(
    fights: list[tuple[int, int, list[dict[str, Any]]]],
    cluster: list[dict[str, Any]],
) -> None:
    if len(cluster) < FIGHT_MIN_KILLS:
        return
    if len(_fight_participant_ids(cluster)) < FIGHT_MIN_PARTICIPANTS:
        return
    start = int(cluster[0].get("timestamp") or 0)
    end = int(cluster[-1].get("timestamp") or 0)
    fights.append((start, end, list(cluster)))


def _fight_participant_ids(kills: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for kill in kills:
        for key in ("killerId", "victimId"):
            value = _optional_int(kill.get(key))
            if value:
                ids.add(value)
        for assist in kill.get("assistingParticipantIds") or []:
            value = _optional_int(assist)
            if value:
                ids.add(value)
    return ids


def _damage_share_in_window(
    participant_id: int,
    team_id: int,
    team_ids: dict[int, int],
    start_ms: int,
    end_ms: int,
    features: list[dict[str, Any]],
) -> float | None:
    if not features:
        return None

    before = _nearest_frame_at_or_before(features, start_ms)
    after = _nearest_frame_at_or_after(features, end_ms)
    if before is None or after is None or before is after:
        return None

    my_delta = _damage_done_delta(before, after, participant_id)
    if my_delta is None:
        return None

    team_delta = 0
    for pid, pid_team in team_ids.items():
        if pid_team != team_id:
            continue
        delta = _damage_done_delta(before, after, pid)
        if delta:
            team_delta += delta

    if team_delta <= 0:
        return None
    return max(0.0, min(1.0, my_delta / team_delta))


def _damage_done_delta(
    before: dict[str, Any],
    after: dict[str, Any],
    participant_id: int,
) -> int | None:
    key = str(participant_id)
    before_stats = ((before.get("raw_frame") or {}).get("participantFrames") or {}).get(key) or {}
    after_stats = ((after.get("raw_frame") or {}).get("participantFrames") or {}).get(key) or {}
    before_damage = (before_stats.get("damageStats") or {}).get("totalDamageDoneToChampions")
    after_damage = (after_stats.get("damageStats") or {}).get("totalDamageDoneToChampions")
    if before_damage is None or after_damage is None:
        return None
    return max(0, int(after_damage) - int(before_damage))


def _nearest_frame_at_or_before(features: list[dict[str, Any]], timestamp_ms: int) -> dict[str, Any] | None:
    candidates = [f for f in features if int(f.get("timestamp_ms") or 0) <= timestamp_ms]
    if not candidates:
        return features[0] if features else None
    return max(candidates, key=lambda f: int(f.get("timestamp_ms") or 0))


def _nearest_frame_at_or_after(features: list[dict[str, Any]], timestamp_ms: int) -> dict[str, Any] | None:
    candidates = [f for f in features if int(f.get("timestamp_ms") or 0) >= timestamp_ms]
    if not candidates:
        return features[-1] if features else None
    return min(candidates, key=lambda f: int(f.get("timestamp_ms") or 0))


def _team_ids_by_participant(match: dict[str, Any]) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for participant in match.get("info", {}).get("participants", []):
        pid = _optional_int(participant.get("participantId"))
        tid = _optional_int(participant.get("teamId"))
        if pid and tid:
            mapping[pid] = tid
    if not mapping:
        mapping = {pid: BLUE_TEAM_ID for pid in range(1, 6)}
        mapping.update({pid: RED_TEAM_ID for pid in range(6, 11)})
    return mapping


# ---------------------------------------------------------------------------
# 4.5 Death acceleration


def _death_acceleration(my_deaths: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    timestamps = sorted(int(death.get("timestamp") or 0) for death in my_deaths)

    chains: list[list[int]] = []
    current: list[int] = []
    for timestamp in timestamps:
        if current and timestamp - current[-1] <= DEATH_CHAIN_WINDOW_MS:
            current.append(timestamp)
        else:
            if len(current) >= 2:
                chains.append(current)
            current = [timestamp]
    if len(current) >= 2:
        chains.append(current)

    score = 0
    evidence: list[dict[str, Any]] = []
    for chain in chains:
        score += 12 * (len(chain) - 1)
        if len(chain) >= 3:
            score += 6
        minutes = ", ".join(str(ts // 60_000) for ts in chain)
        evidence.append(
            _evidence(
                minute=chain[0] // 60_000,
                kind="death_chain",
                title="Deaths snowballed after the first fall",
                description=(
                    f"{len(chain)} deaths landed within rolling 5-minute gaps (minutes {minutes}). "
                    "Only the timing pattern is observed here; what led to each re-entry needs replay review."
                ),
                confidence="high",
            )
        )

    if not evidence:
        evidence.append(
            _evidence(
                minute=0,
                kind="death_chain",
                title="No death chain pattern detected",
                description="No cluster of repeated deaths within short windows was found.",
            )
        )

    return _score(_clamp(score), "high", "higher_is_worse"), evidence


# ---------------------------------------------------------------------------
# shared helpers (kept local so this module stays self-contained)


def _participant_for_puuid(match: dict[str, Any], puuid: str | None) -> dict[str, Any] | None:
    if not puuid:
        return None
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


def _optional_int(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result


def _score(value: int | None, confidence: str, direction: str) -> dict[str, Any]:
    return {"value": value, "confidence": confidence, "direction": direction}


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


def _clamp(value: int) -> int:
    return max(0, min(100, value))
