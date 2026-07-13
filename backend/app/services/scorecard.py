"""Common six-ability scorecard aggregated over recent matches (PRD §6, M2).

Pure functions over records loaded by fetch_player_match_records. Formulas
are v1 hand-tuned rules; every ability keeps {value, confidence, direction}
so the UI and reports treat them exactly like per-match metrics.
"""

from typing import Any

SCORECARD_VERSION = 1

ABILITY_KEYS = [
    "laning",
    "combat",
    "objectives",
    "map_awareness",
    "lead_conversion",
    "stability",
]


def build_scorecard(records: list[dict[str, Any]]) -> dict[str, Any]:
    games = len(records)
    base_confidence = _confidence_for_sample(games)

    abilities: dict[str, dict[str, Any]] = {
        "laning": _laning(records, base_confidence),
        "combat": _combat(records, base_confidence),
        "objectives": _objectives(records, base_confidence),
        "map_awareness": _map_awareness(records, base_confidence),
        "lead_conversion": _lead_conversion(records, base_confidence),
        "stability": _stability(records, base_confidence),
    }

    return {"games": games, "abilities": abilities}


def _laning(records: list[dict[str, Any]], base_confidence: str) -> dict[str, Any]:
    adv = _challenge_avg(records, "laningPhaseGoldExpAdvantage")
    early = _challenge_avg(records, "earlyLaningPhaseGoldExpAdvantage")
    cs_adv = _challenge_avg(records, "maxCsAdvantageOnLaneOpponent")

    if adv is None and early is None and cs_adv is None:
        return _ability(None, "low")

    value = 50.0
    if adv is not None:
        value += (min(1.0, adv) - 0.5) * 40
    if early is not None:
        value += (min(1.0, early) - 0.5) * 20
    if cs_adv is not None:
        value += _bound(cs_adv, -15.0, 15.0)
    return _ability(_clamp(round(value)), base_confidence)


def _combat(records: list[dict[str, Any]], base_confidence: str) -> dict[str, Any]:
    kill_participation = _challenge_avg(records, "killParticipation")  # 0..1
    team_damage_share = _challenge_avg(records, "teamDamagePercentage")  # 0..1, ~0.2 typical
    teamfight = _score_avg(records, "teamfight_persistence_score")

    if kill_participation is None and team_damage_share is None and teamfight is None:
        return _ability(None, "low")

    kp_score = 100 * kill_participation if kill_participation is not None else 50.0
    dmg_score = _bound(100 * (team_damage_share or 0.2) * 2.5, 0.0, 100.0)
    tf_score = teamfight if teamfight is not None else 50.0

    value = 0.4 * kp_score + 0.3 * dmg_score + 0.3 * tf_score
    return _ability(_clamp(round(value)), base_confidence)


def _objectives(records: list[dict[str, Any]], base_confidence: str) -> dict[str, Any]:
    setup = _score_avg(records, "objective_setup_score")
    takedowns = [
        (record["challenges"].get("dragonTakedowns") or 0)
        + (record["challenges"].get("baronTakedowns") or 0)
        + (record["challenges"].get("riftHeraldTakedowns") or 0)
        for record in records
        if record.get("challenges")
    ]
    takedown_avg = sum(takedowns) / len(takedowns) if takedowns else None

    if setup is None and takedown_avg is None:
        return _ability(None, "low")

    setup_score = setup if setup is not None else 50.0
    takedown_score = _bound(100 * (takedown_avg or 0) / 3.0, 0.0, 100.0)
    value = 0.6 * setup_score + 0.4 * takedown_score
    return _ability(_clamp(round(value)), base_confidence)


def _map_awareness(records: list[dict[str, Any]], base_confidence: str) -> dict[str, Any]:
    gambler = _score_avg(records, "gambler_index")
    death_chain = _score_avg(records, "death_acceleration_index")
    vision_adv = _challenge_avg(records, "visionScoreAdvantageLaneOpponent")

    if gambler is None and death_chain is None and vision_adv is None:
        return _ability(None, "low")

    value = 75.0
    value -= 0.35 * (gambler or 0)
    value -= 0.25 * (death_chain or 0)
    if vision_adv is not None:
        value += _bound(vision_adv * 10, -10.0, 10.0)
    return _ability(_clamp(round(value)), base_confidence)


def _lead_conversion(records: list[dict[str, Any]], base_confidence: str) -> dict[str, Any]:
    values = [
        record["scores"]["lead_conversion_score"]
        for record in records
        if record["scores"].get("lead_conversion_score") is not None
    ]
    if len(values) < 2:
        return _ability(None, "low")
    confidence = base_confidence if len(values) >= 5 else "low"
    return _ability(_clamp(round(sum(values) / len(values))), confidence)


def _stability(records: list[dict[str, Any]], base_confidence: str) -> dict[str, Any]:
    value = _score_avg(records, "stability_score")
    if value is None:
        return _ability(None, "low")
    return _ability(_clamp(round(value)), base_confidence)


def scorecard_to_aggregate_rows(scorecard: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, ability in scorecard.get("abilities", {}).items():
        rows.append(
            {
                "metric_key": f"scorecard.{key}",
                "value": ability.get("value"),
                "confidence": ability.get("confidence"),
                "direction": "higher_is_better",
            }
        )
    return rows


def _ability(value: int | None, confidence: str) -> dict[str, Any]:
    return {"value": value, "confidence": confidence, "direction": "higher_is_better"}


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


def _score_avg(records: list[dict[str, Any]], metric_key: str) -> float | None:
    values = [
        record["scores"][metric_key]
        for record in records
        if record.get("scores", {}).get(metric_key) is not None
    ]
    if not values:
        return None
    return sum(values) / len(values)


def _confidence_for_sample(games: int) -> str:
    if games >= 10:
        return "high"
    if games >= 5:
        return "medium"
    return "low"


def _clamp(value: int) -> int:
    return max(0, min(100, value))


def _bound(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
