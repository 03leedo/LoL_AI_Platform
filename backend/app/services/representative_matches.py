"""Representative / best / profile-deviation match selection (Phase 5).

Turns the abstract profile into concrete matches: the game that looks most
like the player's recent self, the strongest context-adjusted performance,
and the game that differed most from the usual profile (explicitly NOT the
"worst" game — deviations can be positive).

Uses the exact per-match dimension formulas from services/profiles.py — no
parallel math. Deterministic for a given record set: all selections break
ties the same way — newer game_creation first, then ascending match_id.
"Best" prefers fuller dimension coverage before comparing means, so a
partial-data match cannot win on 3 dimensions against 5-dimension matches.
"""

import math
from typing import Any

from app.services.profiles import (
    DIMENSION_LABELS,
    MIN_GAMES_FOR_PROFILE,
    per_match_dimension_values,
    recency_weight,
)

SELECTION_VERSION = 1
SELECTION_METHOD = "rms_distance_0_100_v1"

# A match must have at least this many computable dimensions to be compared.
MIN_DIMENSIONS_PER_MATCH = 3
MIN_ELIGIBLE_MATCHES = 5
DRIVER_COUNT = 2


def build_match_selections(
    records: list[dict[str, Any]],
    role: str,
    now_ms: int,
) -> dict[str, Any]:
    role_records = [r for r in records if str(r.get("role") or "").upper() == role]

    eligible: list[dict[str, Any]] = []
    excluded = 0
    for record in role_records:
        vector = per_match_dimension_values(record)
        known = {k: v for k, v in vector.items() if v is not None}
        if len(known) < MIN_DIMENSIONS_PER_MATCH:
            excluded += 1
            continue
        eligible.append({"record": record, "vector": vector})

    base = {
        "role": role,
        "games_considered": len(role_records),
        "eligible_matches": len(eligible),
        "excluded_matches": excluded,
        "selection_version": SELECTION_VERSION,
        "method": SELECTION_METHOD,
        "computed_at_ms": now_ms,
    }

    if len(eligible) < max(MIN_ELIGIBLE_MATCHES, MIN_GAMES_FOR_PROFILE):
        return {**base, "insufficient_data": True, "representative": None, "best": None, "deviation": None}

    profile_vector = _weighted_profile_vector(eligible, now_ms)

    scored = []
    for entry in eligible:
        distance = _rms_distance(entry["vector"], profile_vector)
        mean_value = _mean_of_known(entry["vector"])
        scored.append({**entry, "distance": distance, "mean_value": mean_value})

    # Unified deterministic tie-break: newer game first, then ascending match_id.
    representative = min(
        scored, key=lambda e: (e["distance"], -_creation(e), e["record"]["match_id"])
    )
    deviation = min(
        scored, key=lambda e: (-e["distance"], -_creation(e), e["record"]["match_id"])
    )
    best = min(
        scored,
        key=lambda e: (-_coverage(e), -e["mean_value"], -_creation(e), e["record"]["match_id"]),
    )

    return {
        **base,
        "insufficient_data": False,
        "profile_vector": {k: round(v, 1) for k, v in profile_vector.items()},
        # NOTE: averaged over ELIGIBLE matches only — can differ slightly from
        # the Phase 4 profile, which includes low-coverage matches per dimension.
        "profile_vector_basis": "eligible_matches_recency_weighted",
        "representative": _selection(representative, profile_vector, kind="representative"),
        "best": _selection(best, profile_vector, kind="best"),
        "deviation": _selection(deviation, profile_vector, kind="deviation"),
    }


def _coverage(entry: dict[str, Any]) -> int:
    return sum(1 for value in entry["vector"].values() if value is not None)


def _selection(entry: dict[str, Any], profile_vector: dict[str, float], kind: str) -> dict[str, Any]:
    record = entry["record"]
    vector = entry["vector"]

    diffs = [
        {
            "key": key,
            "label": DIMENSION_LABELS.get(key, key),
            "value": round(vector[key], 1),
            "profile_value": round(profile_vector[key], 1),
            "diff": round(vector[key] - profile_vector[key], 1),
        }
        for key in profile_vector
        if vector.get(key) is not None
    ]

    if kind == "representative":
        drivers = sorted(diffs, key=lambda d: abs(d["diff"]))[:DRIVER_COUNT]
        reason = "평소 프로필과 가장 가까운 경기 — " + ", ".join(
            f"{d['label']} {d['value']:.0f}점(평소 {d['profile_value']:.0f}점)" for d in drivers
        )
    elif kind == "deviation":
        drivers = sorted(diffs, key=lambda d: -abs(d["diff"]))[:DRIVER_COUNT]
        reason = "평소 프로필과 가장 달랐던 경기 — " + ", ".join(
            f"{d['label']} {d['diff']:+.1f}점 차이" for d in drivers
        )
    else:  # best
        drivers = sorted(diffs, key=lambda d: -d["value"])[:DRIVER_COUNT]
        reason = "상황 보정 지표 종합이 가장 높았던 경기 — " + ", ".join(
            f"{d['label']} {d['value']:.0f}점" for d in drivers
        )

    return {
        "kind": kind,
        "match_id": record["match_id"],
        "champion_name": record.get("champion_name"),
        "win": record.get("win"),
        "game_creation": record.get("game_creation"),
        "distance": round(entry["distance"], 2),
        "mean_value": round(entry["mean_value"], 1),
        "dimensions_used": _coverage(entry),
        "reason": reason,
        "drivers": drivers,
        "vector": {k: (round(v, 1) if v is not None else None) for k, v in vector.items()},
    }


def _weighted_profile_vector(
    eligible: list[dict[str, Any]],
    now_ms: int,
) -> dict[str, float]:
    sums: dict[str, float] = {}
    weight_sums: dict[str, float] = {}
    for entry in eligible:
        weight = recency_weight(entry["record"], now_ms)
        for key, value in entry["vector"].items():
            if value is None:
                continue
            sums[key] = sums.get(key, 0.0) + value * weight
            weight_sums[key] = weight_sums.get(key, 0.0) + weight
    return {key: sums[key] / weight_sums[key] for key in sums}


def _rms_distance(vector: dict[str, float | None], profile_vector: dict[str, float]) -> float:
    shared = [
        (vector[key], profile_vector[key])
        for key in profile_vector
        if vector.get(key) is not None
    ]
    if not shared:
        return math.inf
    return math.sqrt(sum((v - p) ** 2 for v, p in shared) / len(shared))


def _mean_of_known(vector: dict[str, float | None]) -> float:
    known = [v for v in vector.values() if v is not None]
    return sum(known) / len(known) if known else 0.0


def _creation(entry: dict[str, Any]) -> int:
    return int(entry["record"].get("game_creation") or 0)
