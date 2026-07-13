"""Role fit analysis over recent matches (PRD §8, M2).

Fit scores are shrunk toward 50 when the sample is small so a 2-0 off-role
stint cannot outrank a 60%-winrate main role (PRD §8.3 sample-confidence
correction).
"""

from typing import Any

ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]

MIN_GAMES_FOR_RECOMMENDATION = 3
CAUTION_FIT_THRESHOLD = 45
FULL_CONFIDENCE_GAMES = 8


def build_role_analysis(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {role: [] for role in ROLES}
    for record in records:
        role = str(record.get("role") or "").upper()
        if role in grouped:
            grouped[role].append(record)

    roles: list[dict[str, Any]] = []
    for role in ROLES:
        role_records = grouped[role]
        games = len(role_records)
        if games == 0:
            roles.append(
                {"role": role, "games": 0, "win_rate": None, "fit_score": None, "confidence": "low"}
            )
            continue

        wins = sum(1 for record in role_records if record.get("win"))
        win_rate = wins / games

        stability = _score_avg(role_records, "stability_score")
        setup = _score_avg(role_records, "objective_setup_score")
        kill_participation = _challenge_avg(role_records, "killParticipation")

        raw_fit = 50.0
        raw_fit += (win_rate - 0.5) * 60
        if stability is not None:
            raw_fit += (stability - 50) * 0.25
        if setup is not None:
            raw_fit += (setup - 50) * 0.15
        if kill_participation is not None:
            raw_fit += (100 * kill_participation - 50) * 0.10

        shrink = min(1.0, games / FULL_CONFIDENCE_GAMES)
        fit = max(0, min(100, round(50 + (raw_fit - 50) * shrink)))

        roles.append(
            {
                "role": role,
                "games": games,
                "win_rate": round(win_rate, 3),
                "fit_score": fit,
                "confidence": _confidence_for_sample(games),
            }
        )

    qualified = [
        role for role in roles
        if role["games"] >= MIN_GAMES_FOR_RECOMMENDATION and role["fit_score"] is not None
    ]
    qualified.sort(key=lambda role: -role["fit_score"])

    # A role must actually look good to be recommended; being someone's best
    # of two bad options is not a recommendation.
    recommended = [role["role"] for role in qualified if role["fit_score"] >= 50][:2]

    caution = None
    low_fit = [role for role in qualified if role["fit_score"] < CAUTION_FIT_THRESHOLD]
    if low_fit:
        caution = min(low_fit, key=lambda role: role["fit_score"])["role"]

    return {"roles": roles, "recommended": recommended, "caution": caution}


def role_analysis_to_aggregate_rows(role_analysis: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in role_analysis.get("roles", []):
        if role.get("fit_score") is None:
            continue
        rows.append(
            {
                "metric_key": f"role_fit.{role['role']}",
                "value": role["fit_score"],
                "confidence": role.get("confidence"),
                "direction": "higher_is_better",
                "role": role["role"],
                "evidence": {"games": role["games"], "win_rate": role.get("win_rate")},
            }
        )
    return rows


def _score_avg(records: list[dict[str, Any]], metric_key: str) -> float | None:
    values = [
        record["scores"][metric_key]
        for record in records
        if record.get("scores", {}).get(metric_key) is not None
    ]
    if not values:
        return None
    return sum(values) / len(values)


def _challenge_avg(records: list[dict[str, Any]], key: str) -> float | None:
    values: list[float] = []
    for record in records:
        raw = record.get("challenges", {}).get(key)
        if raw is None:
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    if not values:
        return None
    return sum(values) / len(values)


def _confidence_for_sample(games: int) -> str:
    if games >= FULL_CONFIDENCE_GAMES:
        return "high"
    if games >= 4:
        return "medium"
    return "low"
