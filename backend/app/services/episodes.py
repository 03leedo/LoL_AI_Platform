"""Episode engine (Phase 3, docs/ai/EXECUTION_PLAN.md).

Groups related kills into fight episodes (time AND distance), models elite
objective availability windows, and attributes each enemy objective to at
most ONE preceding death — so a single dragon loss can never be counted
against four different deaths, and objective-related death rates use an
explicit "analyzable" denominator instead of all deaths.

All thresholds are centralized and versioned here. Position gaps lower
episode confidence instead of inventing proximity.
"""

import math
from typing import Any

EPISODE_VERSION = 1

# Fight clustering (PRODUCT_ANALYSIS_SPEC §6.1)
FIGHT_MAX_GAP_MS = 20_000
FIGHT_MAX_DISTANCE = 3_500
FIGHT_PRE_WINDOW_MS = 15_000
FIGHT_POST_WINDOWS_MS = (30_000, 60_000, 90_000)

# Objective attribution / analyzable predicate
OBJECTIVE_ATTRIBUTION_WINDOW_MS = 90_000

# Patch-approximate elite spawn rules (versioned; refine per patch data later).
DRAGON_FIRST_SPAWN_MS = 300_000
DRAGON_RESPAWN_MS = 300_000
BARON_FIRST_SPAWN_MS = 1_200_000
BARON_RESPAWN_MS = 360_000
HERALD_SPAWN_MS = 480_000
HERALD_DESPAWN_MS = 1_195_000  # ~19:55 if never taken

ELITE_TYPES = {"DRAGON", "RIFTHERALD", "BARON_NASHOR", "ELDER_DRAGON"}


# ---------------------------------------------------------------------------
# Fight episodes


def build_fight_episodes(kill_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Cluster CHAMPION_KILL events into episodes by time gap AND map distance.

    Input events need: timestamp (ms), optional position {x, y}, killerId,
    victimId, optional assistingParticipantIds. Output is deterministic for
    a given input order-independent event set.
    """
    kills = sorted(
        (event for event in kill_events if event.get("type") == "CHAMPION_KILL"),
        key=lambda event: (int(event.get("timestamp") or 0), int(event.get("victimId") or 0)),
    )

    episodes: list[dict[str, Any]] = []
    cluster: list[dict[str, Any]] = []
    degraded = False  # True when a merge decision lacked position data

    def flush() -> None:
        nonlocal cluster, degraded
        if cluster:
            episodes.append(_episode_from_cluster(cluster, len(episodes), degraded))
        cluster = []
        degraded = False

    for kill in kills:
        if not cluster:
            cluster.append(kill)
            continue

        gap_ok = int(kill.get("timestamp") or 0) - int(cluster[-1].get("timestamp") or 0) <= FIGHT_MAX_GAP_MS
        if not gap_ok:
            flush()
            cluster.append(kill)
            continue

        distance = _distance_to_cluster(kill, cluster)
        if distance is None:
            # Missing coordinates: merge on time alone but lower confidence
            # rather than inventing proximity (plan acceptance criterion).
            degraded = True
            cluster.append(kill)
        elif distance <= FIGHT_MAX_DISTANCE:
            cluster.append(kill)
        else:
            flush()
            cluster.append(kill)

    flush()
    return episodes


def _episode_from_cluster(
    cluster: list[dict[str, Any]],
    index: int,
    degraded: bool,
) -> dict[str, Any]:
    positions = [_position(kill) for kill in cluster]
    known = [p for p in positions if p is not None]
    center_x = round(sum(p[0] for p in known) / len(known)) if known else None
    center_y = round(sum(p[1] for p in known) / len(known)) if known else None

    participant_ids: set[int] = set()
    for kill in cluster:
        for key in ("killerId", "victimId"):
            value = kill.get(key)
            if value:
                participant_ids.add(int(value))
        for assist in kill.get("assistingParticipantIds") or []:
            if assist:
                participant_ids.add(int(assist))

    return {
        "episode_index": index,
        "start_ms": int(cluster[0].get("timestamp") or 0),
        "end_ms": int(cluster[-1].get("timestamp") or 0),
        "center_x": center_x,
        "center_y": center_y,
        "kill_count": len(cluster),
        "kills": list(cluster),
        "participant_ids": sorted(participant_ids),
        "confidence": "medium" if (degraded or not known) else "high",
        "episode_version": EPISODE_VERSION,
    }


def _distance_to_cluster(kill: dict[str, Any], cluster: list[dict[str, Any]]) -> float | None:
    kill_pos = _position(kill)
    if kill_pos is None:
        return None
    anchor = None
    for other in reversed(cluster):
        anchor = _position(other)
        if anchor is not None:
            break
    if anchor is None:
        return None
    return math.hypot(kill_pos[0] - anchor[0], kill_pos[1] - anchor[1])


def _position(event: dict[str, Any]) -> tuple[int, int] | None:
    position = event.get("position") or {}
    x, y = position.get("x"), position.get("y")
    if x is None or y is None:
        return None
    return int(x), int(y)


# ---------------------------------------------------------------------------
# Objective availability + analyzable predicate


def elite_availability_windows(
    elite_kills: list[dict[str, Any]],
) -> list[tuple[int, float]]:
    """Availability intervals for elite objectives given observed kill events.

    Input events need: timestamp (ms) and monster_type / monsterType.
    Windows are half-open [spawn_ms, kill_ms or +inf). Side-agnostic:
    availability depends only on when objectives were up, never on team.
    """
    by_type: dict[str, list[int]] = {"DRAGON": [], "RIFTHERALD": [], "BARON_NASHOR": []}
    for event in elite_kills:
        monster = str(event.get("monster_type") or event.get("monsterType") or "").upper()
        if monster == "ELDER_DRAGON":
            monster = "DRAGON"
        if monster in by_type:
            by_type[monster].append(int(event.get("timestamp") or event.get("timestamp_ms") or 0))

    windows: list[tuple[int, float]] = []

    spawn = DRAGON_FIRST_SPAWN_MS
    for kill_ts in sorted(by_type["DRAGON"]):
        windows.append((spawn, float(kill_ts)))
        spawn = kill_ts + DRAGON_RESPAWN_MS
    windows.append((spawn, math.inf))

    spawn = BARON_FIRST_SPAWN_MS
    for kill_ts in sorted(by_type["BARON_NASHOR"]):
        windows.append((spawn, float(kill_ts)))
        spawn = kill_ts + BARON_RESPAWN_MS
    windows.append((spawn, math.inf))

    herald_kills = sorted(by_type["RIFTHERALD"])
    herald_end = float(herald_kills[0]) if herald_kills else float(HERALD_DESPAWN_MS)
    windows.append((HERALD_SPAWN_MS, herald_end))

    return windows


def is_objective_analyzable_death(
    death_timestamp_ms: int,
    windows: list[tuple[int, float]],
    lead_ms: int = OBJECTIVE_ATTRIBUTION_WINDOW_MS,
) -> bool:
    """A death is objective-analyzable when an elite objective is live or
    becomes live within `lead_ms` after the death (SPEC §6.3)."""
    horizon = death_timestamp_ms + lead_ms
    for start, end in windows:
        if start <= horizon and end > death_timestamp_ms:
            return True
    return False


# ---------------------------------------------------------------------------
# Objective → death attribution (deduplication)


def attribute_objectives_to_deaths(
    death_timestamps_ms: list[int],
    objective_timestamps_ms: list[int],
    window_ms: int = OBJECTIVE_ATTRIBUTION_WINDOW_MS,
) -> dict[int, list[int]]:
    """Attribute each objective to at most ONE death: the nearest death that
    precedes it within the window. Returns {death_index: [objective_index...]}.

    Symmetric and deterministic: depends only on timestamps.
    """
    deaths = sorted(range(len(death_timestamps_ms)), key=lambda i: death_timestamps_ms[i])
    attribution: dict[int, list[int]] = {}

    for obj_index, obj_ts in enumerate(objective_timestamps_ms):
        best_death: int | None = None
        for death_index in deaths:
            death_ts = death_timestamps_ms[death_index]
            if death_ts <= obj_ts <= death_ts + window_ms:
                if best_death is None or death_ts > death_timestamps_ms[best_death]:
                    best_death = death_index
        if best_death is not None:
            attribution.setdefault(best_death, []).append(obj_index)

    return attribution
