"""Expected-performance models: GD@10 / CSD@10 / XPD@10 (Phase 8).

One row = one (match, participant) with the lane-opponent differential at
minute 10, taken from the raw stored timeline. Expected values come from
grouped averages fitted on the train split only (MODEL_RULES: compare against
grouped averages before complex models); the output of interest is the
residual `actual - expected`.

This phase is report-only: residuals are NOT wired into profiles or any
user-facing surface. A residual is a context-adjusted observation, not a
skill score, and a single match's residual is never permanent skill.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.advantage_dataset import (
    DEFAULT_QUEUE_ID,
    MIN_GAME_DURATION_S,
    QUEUE_DOMAINS,
    fetch_match_timeline_records,
    patch_of,
    temporal_match_split,
)

EXPECTED_VERSION = 1
SNAPSHOT_MINUTE = 10
TARGETS = ["gd_at_10", "csd_at_10", "xpd_at_10"]
ROLES = ("TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY")

TEST_FRACTION = 0.3
# A train group smaller than this falls back to its parent group — tiny-group
# means are noise, not context.
MIN_GROUP_N = 10
# Residuals may be exposed on user-facing surfaces only past this volume, and
# only via a later explicit phase.
SERVING_MIN_MATCHES = 300

# Baseline hierarchy, simplest first; ties on held-out MAE go to the simpler.
BASELINE_ORDER = ["zero", "role_mean", "role_side_mean"]


def _positions(match_raw: dict[str, Any]) -> dict[int, tuple[int, str]]:
    """participant_id → (team_id, team_position) for valid role entries."""
    out: dict[int, tuple[int, str]] = {}
    for participant in (match_raw.get("info") or {}).get("participants") or []:
        pid = participant.get("participantId")
        team = participant.get("teamId")
        position = participant.get("teamPosition")
        if isinstance(pid, int) and team in (100, 200) and position in ROLES:
            out[pid] = (team, position)
    return out


def _pairings(positions: dict[int, tuple[int, str]]) -> list[tuple[int, int, str]]:
    """(blue_pid, red_pid, role) for roles filled exactly once per team."""
    by_role: dict[str, dict[int, list[int]]] = {}
    for pid, (team, role) in positions.items():
        by_role.setdefault(role, {}).setdefault(team, []).append(pid)
    pairs: list[tuple[int, int, str]] = []
    for role in ROLES:
        teams = by_role.get(role, {})
        if len(teams.get(100, [])) == 1 and len(teams.get(200, [])) == 1:
            pairs.append((teams[100][0], teams[200][0], role))
    return pairs


def _frame_at_minute(timeline_raw: dict[str, Any], minute: int) -> dict[str, Any] | None:
    # Earliest frame in the minute wins: the regular tick precedes any
    # end-of-game frame, so a game ending during this minute (effectively
    # never in ranked solo) would only fall back to its terminal frame.
    for frame in (timeline_raw.get("info") or {}).get("frames") or []:
        if int(frame.get("timestamp") or 0) // 60000 == minute:
            return frame
    return None


def _cs(participant_frame: dict[str, Any]) -> int:
    return int(participant_frame.get("minionsKilled") or 0) + int(
        participant_frame.get("jungleMinionsKilled") or 0
    )


def participant_rows_for_match(
    match_id: str,
    match_raw: dict[str, Any],
    timeline_raw: dict[str, Any],
    game_creation: int,
) -> tuple[list[dict[str, Any]], str | None]:
    """Rows for one match, or ([], reason) when the match is unusable."""
    frame = _frame_at_minute(timeline_raw, SNAPSHOT_MINUTE)
    if frame is None:
        return [], f"no_minute_{SNAPSHOT_MINUTE}_frame"
    participant_frames = frame.get("participantFrames") or {}
    pairs = _pairings(_positions(match_raw))
    if not pairs:
        return [], "no_pairable_roles"

    patch = patch_of(match_raw)
    rows: list[dict[str, Any]] = []
    for blue_pid, red_pid, role in pairs:
        blue = participant_frames.get(str(blue_pid))
        red = participant_frames.get(str(red_pid))
        if not blue or not red:
            continue
        gd = int(blue.get("totalGold") or 0) - int(red.get("totalGold") or 0)
        xpd = int(blue.get("xp") or 0) - int(red.get("xp") or 0)
        csd = _cs(blue) - _cs(red)
        for pid, side, sign in ((blue_pid, "BLUE", 1), (red_pid, "RED", -1)):
            rows.append(
                {
                    "match_id": match_id,
                    "game_creation": game_creation,
                    "patch": patch,
                    "participant_id": pid,
                    "role": role,
                    "side": side,
                    "gd_at_10": sign * gd,
                    "csd_at_10": sign * csd,
                    "xpd_at_10": sign * xpd,
                }
            )
    if not rows:
        return [], "no_minute_frames_for_paired_roles"
    return rows, None


async def build_expected_dataset(
    db: AsyncSession,
    queue_id: int = DEFAULT_QUEUE_ID,
) -> dict[str, Any]:
    records = await fetch_match_timeline_records(db, queue_id)
    rows: list[dict[str, Any]] = []
    matches_included: list[str] = []
    excluded: dict[str, str] = {}
    for record in records:
        match_id = record["match_id"]
        if (record["game_duration"] or 0) < MIN_GAME_DURATION_S:
            excluded[match_id] = "remake_or_short"
            continue
        if not record["game_creation"]:
            excluded[match_id] = "missing_game_creation"
            continue
        match_rows, reason = participant_rows_for_match(
            match_id,
            record["raw_json"] or {},
            record["timeline_json"] or {},
            record["game_creation"],
        )
        if reason:
            excluded[match_id] = reason
            continue
        matches_included.append(match_id)
        rows.extend(match_rows)

    return {
        "expected_version": EXPECTED_VERSION,
        "queue_id": queue_id,
        "domain": QUEUE_DOMAINS[queue_id],
        "targets": TARGETS,
        "snapshot_minute": SNAPSHOT_MINUTE,
        "matches_included": matches_included,
        "matches_excluded": excluded,
        "rows": rows,
    }


def _group_key(baseline: str, row: dict[str, Any]) -> tuple:
    if baseline == "zero":
        return ()
    if baseline == "role_mean":
        return (row["role"],)
    if baseline == "role_side_mean":
        return (row["role"], row["side"])
    raise ValueError(f"unknown baseline {baseline}")


def fit_grouped_baseline(
    baseline: str,
    train_rows: list[dict[str, Any]],
    target: str,
) -> dict[str, Any]:
    """Group means on train rows only; small groups fall back to the parent."""
    groups: dict[tuple, list[float]] = {}
    for row in train_rows:
        groups.setdefault(_group_key(baseline, row), []).append(float(row[target]))
    means = {
        key: sum(values) / len(values)
        for key, values in groups.items()
        if len(values) >= MIN_GROUP_N or baseline == "zero"
    }
    parent = {
        "zero": None,
        "role_mean": "zero",
        "role_side_mean": "role_mean",
    }[baseline]
    return {
        "baseline": baseline,
        "target": target,
        "means": means,
        "group_sizes": {key: len(values) for key, values in groups.items()},
        "parent": fit_grouped_baseline(parent, train_rows, target) if parent else None,
    }


def predict_expected(model: dict[str, Any], row: dict[str, Any]) -> float:
    if model["baseline"] == "zero":
        return 0.0
    key = _group_key(model["baseline"], row)
    if key in model["means"]:
        return model["means"][key]
    return predict_expected(model["parent"], row)


def _mae(errors: list[float]) -> float:
    return sum(abs(e) for e in errors) / len(errors)


def _rmse(errors: list[float]) -> float:
    return (sum(e * e for e in errors) / len(errors)) ** 0.5


def _mean_std(values: list[float]) -> tuple[float, float]:
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return mean, variance ** 0.5


def run_expected_report(
    dataset: dict[str, Any],
    test_fraction: float = TEST_FRACTION,
) -> dict[str, Any]:
    """Fit grouped baselines on train, compare on held-out, report residuals."""
    rows = dataset["rows"]
    total_matches = len(dataset["matches_included"])
    base = {
        "status": "insufficient_data",
        "expected_version": EXPECTED_VERSION,
        "domain": dataset["domain"],
        "queue_id": dataset["queue_id"],
        "matches": total_matches,
        "verdict": {
            "verdict": "report_only",
            "reasons": [f"insufficient_data: {total_matches} matches, cannot split"],
            "serving_min_matches": SERVING_MIN_MATCHES,
        },
    }
    if total_matches < 2 or not rows:
        return base

    split = temporal_match_split(rows, test_fraction)
    train_rows, test_rows = split["train_rows"], split["test_rows"]

    evaluations: dict[str, dict[str, Any]] = {}
    best_baselines: dict[str, str] = {}
    residual_summary: dict[str, dict[str, Any]] = {}
    for target in TARGETS:
        per_baseline: dict[str, Any] = {}
        for baseline in BASELINE_ORDER:
            model = fit_grouped_baseline(baseline, train_rows, target)
            errors = [
                float(row[target]) - predict_expected(model, row) for row in test_rows
            ]
            per_baseline[baseline] = {
                "mae": _mae(errors),
                "rmse": _rmse(errors),
                "n": len(errors),
            }
        evaluations[target] = per_baseline
        # ties go to the earlier (simpler) baseline
        best = min(BASELINE_ORDER, key=lambda b: (per_baseline[b]["mae"], BASELINE_ORDER.index(b)))
        best_baselines[target] = best
        best_model = fit_grouped_baseline(best, train_rows, target)
        residuals = [
            float(row[target]) - predict_expected(best_model, row) for row in test_rows
        ]
        mean, std = _mean_std(residuals)
        residual_summary[target] = {
            "definition": "actual - expected",
            "baseline": best,
            "test_mean": mean,
            "test_std": std,
        }

    reasons = []
    if total_matches < SERVING_MIN_MATCHES:
        reasons.append(
            f"insufficient_data: {total_matches} matches < {SERVING_MIN_MATCHES} for serving"
        )
    reasons.append("report_only_phase: residuals are not wired to any user-facing surface")

    return {
        "status": "evaluated",
        "expected_version": EXPECTED_VERSION,
        "domain": dataset["domain"],
        "queue_id": dataset["queue_id"],
        "snapshot_minute": dataset["snapshot_minute"],
        "matches": total_matches,
        "participant_rows": len(rows),
        "split": {
            "method": "temporal_match_grouped",
            "test_fraction": test_fraction,
            "train_matches": len(split["train_match_ids"]),
            "test_matches": len(split["test_match_ids"]),
            "train_rows": len(train_rows),
            "test_rows": len(test_rows),
        },
        "baseline_evaluations": evaluations,
        "best_baselines": best_baselines,
        "residual_summary": residual_summary,
        "verdict": {
            "verdict": "report_only",
            "reasons": reasons,
            "serving_min_matches": SERVING_MIN_MATCHES,
        },
    }
