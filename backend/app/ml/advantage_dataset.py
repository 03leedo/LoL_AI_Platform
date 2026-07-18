"""Per-minute snapshot dataset for the advantage model (Phase 7).

One training row = one (match, minute) snapshot with only information that is
available at inference time on the win-curve endpoint, plus the match-level
label (blue side won). Features are recomputed deterministically from the raw
stored timelines via `analyze_match_timeline` — the same formula source the
UI win curve uses — so dataset lineage is raw timeline → analyzer → snapshot.

Leakage rules (docs/ml/MODEL_RULES.md):
- all snapshots of one match stay in the same split;
- splits are temporal (by game_creation), never random over snapshot rows;
- features exclude anything not known at the snapshot minute.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RiotMatch, RiotMatchTimeline
from app.services.timeline_analyzer import BLUE_TEAM_ID, analyze_match_timeline

# v2 (2026-07-19): terminal frame excluded — end-of-game state nearly encodes
#     the label, making aggregate metrics optimistic (Phase 7 review M1);
#     minute-interaction features added (gold/xp diff × game-time weight).
DATASET_VERSION = 2
DEFAULT_QUEUE_ID = 420  # ranked solo — the only local domain (soloq, never pro)
MIN_GAME_DURATION_S = 300  # remakes are excluded, consistent with profiles/reports

# Queues must be explicitly mapped to a model domain — pro and solo-queue data
# may never be silently mixed (docs/ml/MODEL_RULES.md). Extending to a new
# queue requires an entry here, and a non-soloq domain requires its own model.
QUEUE_DOMAINS = {420: "soloq"}

# Model inputs, in column order. Diffs are blue-minus-red; `minute` lets the
# model learn time-dependent weighting; the ×time interactions expose the
# late-gold-is-decisive axis the hand-tuned heuristic wins on.
FEATURE_NAMES = [
    "minute",
    "gold_diff",
    "xp_diff",
    "cs_diff",
    "tower_diff",
    "dragon_diff",
    "herald_diff",
    "baron_diff",
    "gold_diff_x_time",
    "xp_diff_x_time",
]


def _time_weight(minute: int) -> float:
    # Same shape as the heuristic's gold aging curve (win_probability.py).
    return min(1.5, 0.5 + minute / 30.0)


def derived_feature_values(row: dict[str, Any]) -> dict[str, float]:
    """Interaction features computed from base snapshot fields.

    Single derivation point shared by training and inference (parity): rows
    never store these columns, so training and any future serving path cannot
    drift apart.
    """
    time_weight = _time_weight(int(row["minute"]))
    return {
        "gold_diff_x_time": float(row["gold_diff"]) * time_weight,
        "xp_diff_x_time": float(row["xp_diff"]) * time_weight,
    }


def full_feature_row(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, **derived_feature_values(row)}


def derive_blue_win(match_raw: dict[str, Any]) -> bool | None:
    """Blue-side result from the match payload; None when it is ambiguous."""
    teams = (match_raw.get("info") or {}).get("teams") or []
    blue_win: bool | None = None
    red_win: bool | None = None
    for team in teams:
        if team.get("teamId") == BLUE_TEAM_ID:
            blue_win = team.get("win")
        else:
            red_win = team.get("win")
    if isinstance(blue_win, bool) and isinstance(red_win, bool) and blue_win != red_win:
        return blue_win
    return None


def patch_of(match_raw: dict[str, Any]) -> str | None:
    version = (match_raw.get("info") or {}).get("gameVersion")
    if not isinstance(version, str):
        return None
    parts = version.split(".")
    if len(parts) < 2:
        return None
    return f"{parts[0]}.{parts[1]}"


def snapshot_rows_for_match(
    match_id: str,
    match_raw: dict[str, Any],
    timeline_raw: dict[str, Any],
    game_creation: int,
) -> list[dict[str, Any]]:
    """Snapshot rows for one match; empty when the match is not usable."""
    blue_win = derive_blue_win(match_raw)
    if blue_win is None:
        return []
    features = analyze_match_timeline(match_id, match_raw, timeline_raw)
    # Drop the terminal frame: its end-of-game state (nexus towers, final
    # gold) nearly encodes the label and inflates aggregate metrics.
    features = features[:-1]
    patch = patch_of(match_raw)
    rows: list[dict[str, Any]] = []
    for feature in features:
        rows.append(
            {
                "match_id": match_id,
                "game_creation": int(game_creation),
                "patch": patch,
                "minute": int(feature["minute"]),
                "gold_diff": int(feature["gold_diff"]),
                "xp_diff": int(feature["xp_diff"]),
                "cs_diff": int(feature["cs_diff"]),
                "tower_diff": feature["blue_tower_kills"] - feature["red_tower_kills"],
                "dragon_diff": feature["blue_dragon_kills"] - feature["red_dragon_kills"],
                "herald_diff": feature["blue_herald_kills"] - feature["red_herald_kills"],
                "baron_diff": feature["blue_baron_kills"] - feature["red_baron_kills"],
                # Raw side counters kept so the heuristic v0 baseline can be
                # evaluated on exactly the same snapshots (inference parity).
                "blue_tower_kills": feature["blue_tower_kills"],
                "red_tower_kills": feature["red_tower_kills"],
                "blue_dragon_kills": feature["blue_dragon_kills"],
                "red_dragon_kills": feature["red_dragon_kills"],
                "blue_herald_kills": feature["blue_herald_kills"],
                "red_herald_kills": feature["red_herald_kills"],
                "blue_baron_kills": feature["blue_baron_kills"],
                "red_baron_kills": feature["red_baron_kills"],
                "timestamp_ms": int(feature["timestamp_ms"]),
                "blue_win": 1 if blue_win else 0,
            }
        )
    return rows


async def fetch_match_timeline_records(
    db: AsyncSession,
    queue_id: int,
) -> Any:
    """Match + raw-timeline records for a domain-mapped queue, oldest first.

    Shared by the ML dataset builders; refuses unmapped queues so soloq and
    pro data can never be silently mixed.
    """
    if queue_id not in QUEUE_DOMAINS:
        raise ValueError(
            f"queue {queue_id} has no domain mapping — refusing to build a mixed"
            f" or unlabeled dataset (known: {sorted(QUEUE_DOMAINS)})"
        )
    query = (
        select(
            RiotMatch.match_id,
            RiotMatch.game_creation,
            RiotMatch.game_duration,
            RiotMatch.raw_json,
            RiotMatchTimeline.raw_json.label("timeline_json"),
        )
        .join(RiotMatchTimeline, RiotMatchTimeline.match_id == RiotMatch.match_id)
        .where(RiotMatch.queue_id == queue_id)
        .order_by(RiotMatch.game_creation.asc(), RiotMatch.match_id.asc())
    )
    result = await db.execute(query)
    return result.mappings()


async def build_dataset(
    db: AsyncSession,
    queue_id: int = DEFAULT_QUEUE_ID,
) -> dict[str, Any]:
    """Deterministic snapshot dataset from stored raw timelines."""
    records = await fetch_match_timeline_records(db, queue_id)
    rows: list[dict[str, Any]] = []
    matches_included: list[str] = []
    excluded: dict[str, str] = {}
    for record in records:
        match_id = record["match_id"]
        match_raw = record["raw_json"] or {}
        timeline_raw = record["timeline_json"] or {}
        if (record["game_duration"] or 0) < MIN_GAME_DURATION_S:
            excluded[match_id] = "remake_or_short"
            continue
        if not record["game_creation"]:
            # The temporal split is only honest with a real creation time.
            excluded[match_id] = "missing_game_creation"
            continue
        match_rows = snapshot_rows_for_match(
            match_id, match_raw, timeline_raw, record["game_creation"]
        )
        if not match_rows:
            excluded[match_id] = "no_winner_or_no_frames"
            continue
        matches_included.append(match_id)
        rows.extend(match_rows)

    return {
        "dataset_version": DATASET_VERSION,
        "queue_id": queue_id,
        "domain": QUEUE_DOMAINS[queue_id],
        "feature_names": FEATURE_NAMES,
        "matches_included": matches_included,
        "matches_excluded": excluded,
        "rows": rows,
    }


def temporal_match_split(
    rows: list[dict[str, Any]],
    test_fraction: float,
) -> dict[str, Any]:
    """Split snapshot rows by match, oldest matches to train, newest to test.

    Matches are ordered by (game_creation, match_id) so the split is
    deterministic; every snapshot follows its match.
    """
    order: list[tuple[int, str]] = sorted(
        {(row["game_creation"], row["match_id"]) for row in rows}
    )
    match_ids = [match_id for _, match_id in order]
    test_count = int(round(len(match_ids) * test_fraction))
    if len(match_ids) > 1:
        test_count = min(max(test_count, 1), len(match_ids) - 1)
    else:
        test_count = 0
    train_ids = set(match_ids[: len(match_ids) - test_count])
    test_ids = set(match_ids[len(match_ids) - test_count:])

    return {
        "train_rows": [row for row in rows if row["match_id"] in train_ids],
        "test_rows": [row for row in rows if row["match_id"] in test_ids],
        "train_match_ids": sorted(train_ids),
        "test_match_ids": sorted(test_ids),
    }
