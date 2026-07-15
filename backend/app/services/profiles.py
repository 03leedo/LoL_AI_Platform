"""Individual performance profile v1 (Phase 4, docs/ai/EXECUTION_PLAN.md).

Five role-filtered dimensions computed from per-match features already stored
by the ingest pipeline, aggregated with recency weighting and sample-size
shrinkage toward the cohort mean. Percentiles come from the LOCAL sample
cohort (all stored participants of the same role/queue) — tier is unknown for
arbitrary participants, so the comparison group is always labeled as a local
sample, never a tier cohort.

Outputs follow the domain contract: score + sample_size + confidence +
comparison_group + submetrics + evidence match ids. A profile is a summary of
recent observed performance, not permanent skill.
"""

import math
from typing import Any

PROFILE_VERSION = 1

RECENCY_DECAY_DAYS = 14.0
# Shrinkage: reliability = n_eff/(n_eff+K), n_eff = (Σw)²/Σw² over recency
# weights. K=8 keeps the "8 comparable games ≈ trustworthy" scale of
# role_analyzer, but the functional forms are intentionally different
# (role fit uses min(1, n/8)).
SHRINKAGE_K = 8.0
MIN_COHORT_ROWS = 30
MIN_GAMES_FOR_PROFILE = 3

# v1 dimension scaling constants — versioned via PROFILE_VERSION.
EARLY_LANE_ADV_WEIGHT = 40.0
EARLY_PHASE_ADV_WEIGHT = 20.0
EARLY_CS_ADV_CAP = 15.0
DPG_SCALE = 33.0  # damage-per-gold ~1.5 average → ~50pts
RISK_COMPONENT_WEIGHTS = (
    ("gambler_index", 0.4),
    ("death_acceleration_index", 0.3),
    ("death_cost_index", 0.3),
)
OBJECTIVE_SETUP_WEIGHT = 0.8
OBJECTIVE_TAKEDOWN_POINTS = 5.0
OBJECTIVE_TAKEDOWN_CAP = 20.0

DIMENSION_KEYS = [
    "early_growth",
    "resource_conversion",
    "risk_management",
    "objective_readiness",
    "fight_contribution",
]

# risk_management is the INVERSE of risk/style signals (100 - weighted risk):
# higher = fewer observed exposures. The key says "management" so the stored
# higher_is_better direction cannot read as "more risk is better"
# (domain reviewer finding, 2026-07-14).
DIMENSION_META: dict[str, dict[str, str]] = {
    "early_growth": {"direction_group": "performance"},
    "resource_conversion": {"direction_group": "performance"},
    "risk_management": {"direction_group": "performance"},
    "objective_readiness": {"direction_group": "performance"},
    "fight_contribution": {"direction_group": "performance"},
}


def dominant_role(records: list[dict[str, Any]]) -> str | None:
    counts: dict[str, int] = {}
    for record in records:
        role = str(record.get("role") or "").upper()
        if role:
            counts[role] = counts.get(role, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def build_player_profile(
    records: list[dict[str, Any]],
    cohort_rows: list[dict[str, Any]],
    role: str,
    now_ms: int,
    queue_label: str = "솔로랭크",
) -> dict[str, Any]:
    """Compute the five-dimension profile for ONE role (never mixes roles)."""
    role_records = [r for r in records if str(r.get("role") or "").upper() == role]
    games = len(role_records)

    comparison_group = (
        f"{queue_label} {ROLE_LABELS.get(role, role)} · 로컬 수집 표본 {len(cohort_rows)}명 "
        "(티어 미구분 — 코호트 데이터 수집 전 임시 기준 · 백분위는 개인 다경기 평균을 "
        "단일 경기 분포와 비교한 값이라 과대/과소될 수 있음)"
        if len(cohort_rows) >= MIN_COHORT_ROWS
        else f"{queue_label} {ROLE_LABELS.get(role, role)} · 비교 표본 부족(백분위 생략)"
    )

    if games < MIN_GAMES_FOR_PROFILE:
        return {
            "role": role,
            "games": games,
            "profile_version": PROFILE_VERSION,
            "comparison_group": comparison_group,
            "computed_at_ms": now_ms,
            "insufficient_data": True,
            "dimensions": [],
        }

    weights = [_recency_weight(record, now_ms) for record in role_records]
    cohort_ok = len(cohort_rows) >= MIN_COHORT_ROWS

    dimensions = [
        _early_growth(role_records, weights, cohort_rows, cohort_ok, comparison_group),
        _resource_conversion(role_records, weights, cohort_rows, cohort_ok, comparison_group),
        _risk_management(role_records, weights, cohort_rows, cohort_ok, comparison_group),
        _objective_readiness(role_records, weights, cohort_rows, cohort_ok, comparison_group),
        _fight_contribution(role_records, weights, cohort_rows, cohort_ok, comparison_group),
    ]

    return {
        "role": role,
        "games": games,
        "profile_version": PROFILE_VERSION,
        "comparison_group": comparison_group,
        "computed_at_ms": now_ms,
        "insufficient_data": False,
        "dimensions": dimensions,
    }


ROLE_LABELS = {"TOP": "탑", "JUNGLE": "정글", "MIDDLE": "미드", "BOTTOM": "원딜", "UTILITY": "서포터"}


# ---------------------------------------------------------------------------
# Dimensions — each returns the shared contract dict.


def _early_growth(records, weights, cohort_rows, cohort_ok, comparison_group):
    def per_match(record) -> float | None:
        challenges = record.get("challenges", {})
        lane = _as_float(challenges.get("laningPhaseGoldExpAdvantage"))
        early = _as_float(challenges.get("earlyLaningPhaseGoldExpAdvantage"))
        cs_adv = _as_float(challenges.get("maxCsAdvantageOnLaneOpponent"))
        if lane is None and early is None and cs_adv is None:
            return None
        value = 50.0
        if lane is not None:
            value += (min(1.0, lane) - 0.5) * EARLY_LANE_ADV_WEIGHT
        if early is not None:
            value += (min(1.0, early) - 0.5) * EARLY_PHASE_ADV_WEIGHT
        if cs_adv is not None:
            value += max(-EARLY_CS_ADV_CAP, min(EARLY_CS_ADV_CAP, cs_adv))
        return _clamp(value)

    submetrics = []
    if cohort_ok:
        submetrics = [
            _submetric(
                "lane_advantage_rate",
                "라인전 우위 판 비율",
                _weighted_avg([_as_float(r["challenges"].get("laningPhaseGoldExpAdvantage")) for r in records], weights),
                _cohort_values(cohort_rows, lambda c: _as_float(c["challenges"].get("laningPhaseGoldExpAdvantage"))),
            ),
            _submetric(
                "max_cs_advantage",
                "라인 상대 최대 CS 우위",
                _weighted_avg([_as_float(r["challenges"].get("maxCsAdvantageOnLaneOpponent")) for r in records], weights),
                _cohort_values(cohort_rows, lambda c: _as_float(c["challenges"].get("maxCsAdvantageOnLaneOpponent"))),
            ),
        ]

    # Same formula is computable on cohort rows (challenges-only inputs), so a
    # dimension-level percentile is honest here.
    cohort_values = (
        [v for v in (per_match(row) for row in cohort_rows) if v is not None]
        if cohort_ok
        else None
    )

    return _dimension(
        key="early_growth",
        label="초반 성장 안정성",
        records=records,
        weights=weights,
        per_match=per_match,
        submetrics=submetrics,
        comparison_group=comparison_group,
        cohort_values=cohort_values,
    )


def _resource_conversion(records, weights, cohort_rows, cohort_ok, comparison_group):
    def per_match(record) -> float | None:
        dpg = _damage_per_gold(record)
        if dpg is None:
            return None
        return _clamp(dpg * DPG_SCALE)

    submetrics = []
    cohort_dpg = _cohort_values(cohort_rows, _damage_per_gold) if cohort_ok else []
    if cohort_ok:
        submetrics = [
            _submetric(
                "damage_per_gold",
                "골드당 챔피언 피해량",
                _weighted_avg([_damage_per_gold(r) for r in records], weights),
                cohort_dpg,
            ),
            _submetric(
                "kill_participation",
                "킬 관여율",
                _weighted_avg([_as_float(r["challenges"].get("killParticipation")) for r in records], weights),
                _cohort_values(cohort_rows, lambda c: _as_float(c["challenges"].get("killParticipation"))),
            ),
        ]

    return _dimension(
        key="resource_conversion",
        label="자원 전환 효율",
        records=records,
        weights=weights,
        per_match=per_match,
        submetrics=submetrics,
        comparison_group=comparison_group,
        cohort_values=[_clamp(v * DPG_SCALE) for v in cohort_dpg] if cohort_ok else None,
    )


def _risk_management(records, weights, cohort_rows, cohort_ok, comparison_group):
    def per_match(record) -> float | None:
        scores = record.get("scores", {})
        parts = []
        for key, weight in RISK_COMPONENT_WEIGHTS:
            value = scores.get(key)
            if value is not None:
                parts.append((float(value), weight))
        if not parts:
            return None
        total_weight = sum(w for _, w in parts)
        risk = sum(v * w for v, w in parts) / total_weight
        return _clamp(100.0 - risk)

    submetrics = []
    if cohort_ok:
        submetrics = [
            _submetric(
                "deaths_per_10min",
                "10분당 데스 (낮을수록 좋음)",
                _weighted_avg([_deaths_per_10(r) for r in records], weights),
                _cohort_values(cohort_rows, _deaths_per_10),
                lower_is_better=True,
            ),
        ]

    return _dimension(
        key="risk_management",
        label="위험 노출 관리",
        records=records,
        weights=weights,
        per_match=per_match,
        submetrics=submetrics,
        comparison_group=comparison_group,
        cohort_values=None,
    )


def _objective_readiness(records, weights, cohort_rows, cohort_ok, comparison_group):
    def per_match(record) -> float | None:
        setup = record.get("scores", {}).get("objective_setup_score")
        if setup is None:
            return None
        takedowns = _elite_takedowns(record)
        bonus = min(OBJECTIVE_TAKEDOWN_CAP, (takedowns or 0) * OBJECTIVE_TAKEDOWN_POINTS)
        return _clamp(OBJECTIVE_SETUP_WEIGHT * float(setup) + bonus)

    submetrics = []
    if cohort_ok:
        submetrics = [
            _submetric(
                "elite_takedowns_per_game",
                "경기당 엘리트 오브젝트 관여",
                _weighted_avg([_elite_takedowns(r) for r in records], weights),
                _cohort_values(cohort_rows, _elite_takedowns),
            ),
        ]

    return _dimension(
        key="objective_readiness",
        label="오브젝트 준비",
        records=records,
        weights=weights,
        per_match=per_match,
        submetrics=submetrics,
        comparison_group=comparison_group,
        cohort_values=None,
    )


def _fight_contribution(records, weights, cohort_rows, cohort_ok, comparison_group):
    def per_match(record) -> float | None:
        teamfight = record.get("scores", {}).get("teamfight_persistence_score")
        if teamfight is not None:
            return _clamp(float(teamfight))
        kp = _as_float(record.get("challenges", {}).get("killParticipation"))
        if kp is None:
            return None
        return _clamp(kp * 100.0)

    submetrics = []
    if cohort_ok:
        submetrics = [
            _submetric(
                "team_damage_share",
                "팀 내 피해량 비중",
                _weighted_avg([_as_float(r["challenges"].get("teamDamagePercentage")) for r in records], weights),
                _cohort_values(cohort_rows, lambda c: _as_float(c["challenges"].get("teamDamagePercentage"))),
            ),
        ]

    return _dimension(
        key="fight_contribution",
        label="교전 결과 기여",
        records=records,
        weights=weights,
        per_match=per_match,
        submetrics=submetrics,
        comparison_group=comparison_group,
        cohort_values=None,
    )


# ---------------------------------------------------------------------------
# Shared machinery


def _dimension(
    key: str,
    label: str,
    records: list[dict[str, Any]],
    weights: list[float],
    per_match,
    submetrics: list[dict[str, Any]],
    comparison_group: str,
    cohort_values: list[float] | None,
) -> dict[str, Any]:
    values: list[float] = []
    used_weights: list[float] = []
    evidence_match_ids: list[str] = []
    for record, weight in zip(records, weights):
        value = per_match(record)
        if value is None:
            continue
        values.append(value)
        used_weights.append(weight)
        evidence_match_ids.append(record["match_id"])

    if not values:
        return {
            "key": key,
            "label": label,
            "score": None,
            "raw_score": None,
            "percentile": None,
            "sample_size": 0,
            "effective_sample_size": 0.0,
            "confidence": "low",
            "comparison_group": comparison_group,
            "direction_group": DIMENSION_META[key]["direction_group"],
            "submetrics": submetrics,
            "evidence_match_ids": [],
            "insufficient_data": True,
        }

    weight_sum = sum(used_weights)
    personal = sum(v * w for v, w in zip(values, used_weights)) / weight_sum

    # Baseline only trusts a cohort of meaningful size; otherwise neutral 50.
    baseline = 50.0
    if cohort_values and len(cohort_values) >= MIN_COHORT_ROWS:
        baseline = sum(cohort_values) / len(cohort_values)

    # Effective sample size honors recency: ten stale games do not count as
    # ten fresh ones (n_eff = (Σw)²/Σw²).
    weight_sq_sum = sum(w * w for w in used_weights)
    n_eff = (weight_sum * weight_sum) / weight_sq_sum if weight_sq_sum else 0.0
    reliability = n_eff / (n_eff + SHRINKAGE_K)
    adjusted = reliability * personal + (1 - reliability) * baseline

    percentile = None
    if cohort_values and len(cohort_values) >= MIN_COHORT_ROWS:
        percentile = _percentile_rank(personal, cohort_values)

    return {
        "key": key,
        "label": label,
        "score": round(adjusted),
        "raw_score": round(personal),
        "percentile": percentile,
        "sample_size": len(values),
        "effective_sample_size": round(n_eff, 1),
        "confidence": _confidence(n_eff),
        "comparison_group": comparison_group,
        "direction_group": DIMENSION_META[key]["direction_group"],
        "submetrics": submetrics,
        "evidence_match_ids": evidence_match_ids,
        "insufficient_data": False,
    }


def _submetric(
    key: str,
    label: str,
    value: float | None,
    cohort_values: list[float],
    lower_is_better: bool = False,
) -> dict[str, Any]:
    percentile = None
    if value is not None and len(cohort_values) >= MIN_COHORT_ROWS:
        rank = _percentile_rank(value, cohort_values)
        percentile = 100 - rank if lower_is_better else rank
    return {
        "key": key,
        "label": label,
        "value": round(value, 3) if value is not None else None,
        "percentile": percentile,
        "lower_is_better": lower_is_better,
    }


def _recency_weight(record: dict[str, Any], now_ms: int) -> float:
    game_creation = record.get("game_creation")
    if not game_creation:
        return 1.0
    days = max(0.0, (now_ms - int(game_creation)) / 86_400_000)
    return math.exp(-days / RECENCY_DECAY_DAYS)


def _percentile_rank(value: float, population: list[float]) -> int:
    below = sum(1 for other in population if other < value)
    equal = sum(1 for other in population if other == value)
    return round(100 * (below + 0.5 * equal) / len(population))


def _confidence(effective_sample_size: float) -> str:
    # Thresholds intentionally sit near the scorecard ladder (10/5) rather
    # than role_analyzer's 8/4 — evaluated on n_eff, not raw counts.
    if effective_sample_size >= 10:
        return "high"
    if effective_sample_size >= 5:
        return "medium"
    return "low"


def _cohort_values(cohort_rows: list[dict[str, Any]], extractor) -> list[float]:
    values = []
    for row in cohort_rows:
        value = extractor(row)
        if value is not None:
            values.append(float(value))
    return values


def _damage_per_gold(row: dict[str, Any]) -> float | None:
    damage = row.get("damage_to_champions")
    gold = row.get("gold_earned")
    if not damage or not gold:
        return None
    return float(damage) / float(gold)


def _deaths_per_10(row: dict[str, Any]) -> float | None:
    deaths = row.get("deaths")
    duration = row.get("game_duration")
    if deaths is None or not duration:
        return None
    return float(deaths) * 600.0 / float(duration)


def _elite_takedowns(row: dict[str, Any]) -> float | None:
    challenges = row.get("challenges", {})
    values = [
        _as_float(challenges.get("dragonTakedowns")),
        _as_float(challenges.get("baronTakedowns")),
        _as_float(challenges.get("riftHeraldTakedowns")),
    ]
    known = [v for v in values if v is not None]
    if not known:
        return None
    return sum(known)


def _weighted_avg(values: list[float | None], weights: list[float]) -> float | None:
    pairs = [(v, w) for v, w in zip(values, weights) if v is not None]
    if not pairs:
        return None
    return sum(v * w for v, w in pairs) / sum(w for _, w in pairs)


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def profile_to_aggregate_rows(profile: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for dimension in profile.get("dimensions", []):
        if dimension.get("score") is None:
            continue
        rows.append(
            {
                "metric_key": f"profile.{dimension['key']}",
                "value": dimension["score"],
                "confidence": dimension["confidence"],
                "direction": "higher_is_better",
                "role": profile.get("role"),
                "evidence": {
                    "raw_score": dimension.get("raw_score"),
                    "percentile": dimension.get("percentile"),
                    "sample_size": dimension.get("sample_size"),
                    "effective_sample_size": dimension.get("effective_sample_size"),
                    "comparison_group": dimension.get("comparison_group"),
                    "evidence_match_ids": dimension.get("evidence_match_ids", []),
                    "profile_version": PROFILE_VERSION,
                    "computed_at_ms": profile.get("computed_at_ms"),
                    # risk_management is 100 - weighted risk signals; record
                    # the sources so the stored row cannot be misread.
                    **(
                        {"inverted_from": [key for key, _ in RISK_COMPONENT_WEIGHTS]}
                        if dimension["key"] == "risk_management"
                        else {}
                    ),
                },
            }
        )
    return rows
