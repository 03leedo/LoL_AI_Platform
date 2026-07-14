"""Cross-match repeated-pattern detection (M3, master-plan 차별화 ②③).

Single-match scores can be luck; repetition is a habit. Every pattern here is
computed by explicit rules over locally stored data and carries the match ids
it was observed in — the AI report may only rephrase these, never invent.

Pattern severity: "positive" (강점) | "warn" | "critical". All user-facing
text is Korean because patterns render directly in the report UI.
"""

from typing import Any

from app.services.heatmaps import zone_of

OBJECTIVE_WINDOW_MS = 90_000

FIRST_DEATH_WINDOW_MINUTES = 6
FIRST_DEATH_MIN_SHARE = 0.5
FIRST_DEATH_MIN_COUNT = 3

DEATH_ZONE_MIN_SHARE = 0.30
DEATH_ZONE_MIN_COUNT = 5

OBJECTIVE_DEATH_MIN_SHARE = 0.30
OBJECTIVE_DEATH_MIN_COUNT = 4

SHUTDOWN_MIN_GOLD = 700
SHUTDOWN_MIN_EVENTS = 3

ZONE_LABELS = {
    "top": "탑",
    "mid": "미드",
    "bot": "봇",
    "ally_jungle": "아군 정글",
    "enemy_jungle": "적 정글",
}

# (metric_key, threshold, comparator, severity, title, description template)
CHRONIC_WEAKNESS_RULES = [
    (
        "gold_retention_score", 35, "gte", "warn",
        "킬 골드를 아이템으로 늦게 바꾸는 경향",
        "골드 리텐션 평균 {avg:.0f}점 — 이득을 본 뒤 귀환/아이템 전환이 늦는 경향이 반복 관측됩니다.",
    ),
    (
        "gambler_index", 35, "gte", "warn",
        "하이리스크 플레이 성향 (고립·제압골 노출)",
        "도박사 지수 평균 {avg:.0f}점 — 아군과 떨어진 위치에서의 데스나 제압골 헌납이 반복됩니다.",
    ),
    (
        "death_acceleration_index", 25, "gte", "critical",
        "첫 데스 후 연쇄 데스가 이어지는 경향",
        "데스 가속도 평균 {avg:.0f}점 — 한 번 죽은 뒤 5분 내 추가 데스가 이어지는 판이 잦습니다.",
    ),
    (
        "teamfight_persistence_score", 45, "lte", "warn",
        "한타에서 딜을 이어가지 못하는 경향",
        "한타 지속력 평균 {avg:.0f}점 — 한타에서 일찍 잘리거나 딜 지분이 낮은 판이 많습니다.",
    ),
    (
        "objective_setup_score", 45, "lte", "warn",
        "오브젝트 준비 단계의 손실",
        "오브젝트 준비 평균 {avg:.0f}점 — 드래곤/바론 직전 교전이나 시야 싸움에서 손해가 반복됩니다.",
    ),
    (
        "lead_conversion_score", 45, "lte", "warn",
        "초반 리드를 승리 조건으로 못 바꾸는 경향",
        "리드 전환 평균 {avg:.0f}점 — 앞선 골드가 15~25분 오브젝트/포탑으로 이어지지 못합니다.",
    ),
]

CHRONIC_STRENGTH_RULES = [
    ("gold_retention_score", 12, "lte", "골드를 아이템으로 빠르게 굴리는 템포", "골드 리텐션 평균 {avg:.0f}점 — 이득을 즉시 아이템 파워로 전환합니다."),
    ("teamfight_persistence_score", 60, "gte", "한타에서 끝까지 살아남는 지속력", "한타 지속력 평균 {avg:.0f}점 — 한타에서 생존하며 딜 지분을 유지합니다."),
    ("objective_setup_score", 60, "gte", "깔끔한 오브젝트 준비", "오브젝트 준비 평균 {avg:.0f}점 — 손실 없는 오브젝트 확보가 많습니다."),
    ("lead_conversion_score", 60, "gte", "리드를 굴릴 줄 아는 운영", "리드 전환 평균 {avg:.0f}점 — 초반 이득을 오브젝트로 연결합니다."),
    ("stability_score", 70, "gte", "안정적인 데스 관리", "안정성 평균 {avg:.0f}점 — 비용이 큰 데스가 적습니다."),
]

# Phase 1: replay questions are the honest counterpart to recommendations —
# they point at scenes to verify instead of asserting causes.
REPLAY_QUESTIONS_BY_KEY = {
    "first_death_window": "해당 시간대 직전 1분의 웨이브 상태·아군 위치·미니맵 노출 인원을 리플레이에서 확인해 보세요.",
    "death_zone": "그 구역으로 진입하기 직전, 미니맵에 보이지 않던 상대가 몇 명이었는지 확인해 보세요.",
    "objective_linked_deaths": "오브젝트 생성 60~90초 전 장면에서 본인 위치와 시야 상태를 확인해 보세요.",
    "shutdown_conceded": "제압골을 내준 데스 직전, 후퇴할 수 있는 타이밍이 있었는지 확인해 보세요.",
    "gold_retention_score": "킬/포탑 골드 획득 직후 귀환 대신 필드에 머문 장면에서 어떤 판단이 있었는지 확인해 보세요.",
    "gambler_index": "고립 데스 장면에서 가장 가까운 아군과의 거리와 진입 목적을 확인해 보세요.",
    "death_acceleration_index": "부활 직후 첫 이동 경로가 어디를 향했는지 확인해 보세요.",
    "teamfight_persistence_score": "한타 시작 시 본인 위치가 팀 대형의 어디였는지 확인해 보세요.",
    "objective_setup_score": "오브젝트 90초 전 시야·라인 상태가 준비돼 있었는지 확인해 보세요.",
    "lead_conversion_score": "리드를 잡은 직후 팀이 어떤 목표로 움직였는지 확인해 보세요.",
}

RECOMMENDATIONS_BY_KEY = {
    "first_death_window": "해당 시간대 직전에는 시야를 먼저 확보하고 웨이브 손해를 감수하더라도 반 박자 뒤로 서 보세요. 첫 데스만 넘겨도 판의 절반이 달라집니다.",
    "death_zone": "그 구역에 진입하기 전 상대 위치가 미니맵에 몇 명 보이는지 세는 습관을 들이세요. 안 보이는 인원 수 = 그 구역의 위험도입니다.",
    "objective_linked_deaths": "오브젝트 생성 90초 전에는 '내가 지금 죽으면 이 오브젝트가 넘어간다'를 기준으로 교전을 선택하세요.",
    "shutdown_conceded": "연속 킬 후에는 현상금이 커집니다. 스노우볼 중일수록 귀환 타이밍을 앞당겨 제압골 노출을 줄이세요.",
    "gold_retention_score": "킬/포탑 골드를 얻으면 다음 웨이브를 밀어넣고 바로 귀환하는 루틴을 만들어 보세요. 1,500골드 이상 들고 싸우지 않기.",
    "gambler_index": "공격적인 성향 자체는 무기입니다. 다만 아군이 4,000유닛 안에 없을 때는 진입을 한 박자 늦추는 규칙만 추가해 보세요.",
    "death_acceleration_index": "죽은 직후의 첫 판단이 연쇄를 만듭니다. 부활 후 1웨이브는 무조건 정비/시야로 쓰는 규칙을 시도해 보세요.",
    "teamfight_persistence_score": "한타에서 첫 스킬 교환 후 2초간 뒤로 빠졌다가 재진입하는 리듬을 연습하세요. 생존 시간이 곧 딜입니다.",
    "objective_setup_score": "오브젝트 90초 전 체크리스트: 강가 시야, 라인 주도권, 정글러 위치. 하나라도 없으면 싸움을 강요하지 마세요.",
    "lead_conversion_score": "리드를 잡으면 '다음 목표'를 소리 내어 정하세요(포탑/전령/시야). 목표 없는 리드는 시간이 지나면 사라집니다.",
}


def detect_patterns(
    records: list[dict[str, Any]],
    event_history: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    total_matches = len(records)
    if total_matches == 0:
        return patterns

    patterns.extend(_first_death_window(event_history, total_matches))
    patterns.extend(_death_zone(event_history))
    patterns.extend(_objective_linked_deaths(event_history))
    patterns.extend(_shutdown_conceded(event_history))
    patterns.extend(_chronic_metrics(records))

    severity_order = {"critical": 0, "warn": 1, "positive": 2}
    patterns.sort(key=lambda item: (severity_order.get(item["severity"], 3), -len(item["matches"])))
    return patterns


def summarize_death_autopsy(event_history: dict[str, dict[str, Any]]) -> dict[str, Any]:
    deaths = sum(len(ctx["deaths"]) for ctx in event_history.values())
    kills = sum(len(ctx["kills"]) for ctx in event_history.values())
    shutdown_deaths = 0
    shutdown_gold = 0
    objective_linked = 0
    first_death_minutes: list[int] = []

    for context in event_history.values():
        if context["deaths"]:
            first_death_minutes.append(context["deaths"][0]["minute"])
        for death in context["deaths"]:
            if death.get("shutdown_bounty"):
                shutdown_deaths += 1
                shutdown_gold += death["shutdown_bounty"]
            if _objective_after(context["enemy_objectives"], death["timestamp_ms"]):
                objective_linked += 1

    return {
        "matches": len(event_history),
        "deaths": deaths,
        "kills": kills,
        "shutdown_deaths": shutdown_deaths,
        "shutdown_gold_conceded": shutdown_gold,
        "objective_linked_deaths": objective_linked,
        "objective_linked_share": round(objective_linked / deaths, 2) if deaths else 0.0,
        "avg_first_death_minute": (
            round(sum(first_death_minutes) / len(first_death_minutes), 1)
            if first_death_minutes
            else None
        ),
    }


def _first_death_window(
    event_history: dict[str, dict[str, Any]],
    total_matches: int,
) -> list[dict[str, Any]]:
    firsts = [
        (match_id, context["deaths"][0]["minute"])
        for match_id, context in event_history.items()
        if context["deaths"]
    ]
    if len(firsts) < FIRST_DEATH_MIN_COUNT:
        return []

    best_start, best_hits = None, []
    for start in range(0, 30):
        hits = [match_id for match_id, minute in firsts if start <= minute < start + FIRST_DEATH_WINDOW_MINUTES]
        if len(hits) > len(best_hits):
            best_start, best_hits = start, hits

    share = len(best_hits) / len(firsts)
    if best_start is None or len(best_hits) < FIRST_DEATH_MIN_COUNT or share < FIRST_DEATH_MIN_SHARE:
        return []

    end = best_start + FIRST_DEATH_WINDOW_MINUTES
    return [
        {
            "key": "first_death_window",
            "severity": "warn",
            "title": f"첫 데스가 {best_start}~{end}분 사이에 반복",
            "description": (
                f"첫 데스가 발생한 {len(firsts)}판 중 {len(best_hits)}판({share:.0%})에서 "
                f"첫 데스가 {best_start}~{end}분 구간에 몰려 있습니다. 이 시간대의 판단을 복기 1순위로 두세요."
            ),
            "stat": f"{len(best_hits)}/{len(firsts)}판 ({share:.0%})",
            "matches": best_hits,
        }
    ]


def _death_zone(event_history: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    zone_counts: dict[str, int] = {}
    zone_matches: dict[str, set[str]] = {}
    total_deaths = 0

    for match_id, context in event_history.items():
        for death in context["deaths"]:
            if death.get("x") is None or death.get("y") is None:
                continue
            total_deaths += 1
            zone = zone_of(death["x"], death["y"], context["team_id"])
            zone_counts[zone] = zone_counts.get(zone, 0) + 1
            zone_matches.setdefault(zone, set()).add(match_id)

    if total_deaths == 0:
        return []

    top_zone, top_count = max(zone_counts.items(), key=lambda item: item[1])
    share = top_count / total_deaths
    if top_count < DEATH_ZONE_MIN_COUNT or share < DEATH_ZONE_MIN_SHARE:
        return []

    label = ZONE_LABELS.get(top_zone, top_zone)
    return [
        {
            "key": "death_zone",
            "severity": "warn",
            "title": f"'{label}' 데스 존 반복",
            "description": (
                f"최근 데스 {total_deaths}회 중 {top_count}회({share:.0%})가 '{label}' 구역에서 발생했습니다. "
                "특정 구역 진입 판단이 반복 요인일 수 있습니다. 해당 장면들을 리플레이로 확인해 보세요."
            ),
            "stat": f"{top_count}/{total_deaths}회 ({share:.0%})",
            "matches": sorted(zone_matches.get(top_zone, set())),
        }
    ]


def _objective_linked_deaths(event_history: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    linked = 0
    total_deaths = 0
    matches: set[str] = set()

    for match_id, context in event_history.items():
        for death in context["deaths"]:
            total_deaths += 1
            if _objective_after(context["enemy_objectives"], death["timestamp_ms"]):
                linked += 1
                matches.add(match_id)

    if total_deaths == 0:
        return []
    share = linked / total_deaths
    if linked < OBJECTIVE_DEATH_MIN_COUNT or share < OBJECTIVE_DEATH_MIN_SHARE:
        return []

    return [
        {
            "key": "objective_linked_deaths",
            "severity": "critical",
            "title": "데스 직후 상대 오브젝트 획득이 동반되는 경향",
            "description": (
                f"데스 {total_deaths}회 중 {linked}회({share:.0%})에서 90초 안에 상대 오브젝트 획득이 관측됐습니다. "
                "인과가 아니라 동반 관측이며, 전체 데스를 분모로 쓴 근사치입니다(오브젝트 생성 여부 미고려)."
            ),
            "stat": f"{linked}/{total_deaths}회 ({share:.0%})",
            "matches": sorted(matches),
        }
    ]


def _shutdown_conceded(event_history: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    events = 0
    gold = 0
    matches: set[str] = set()

    for match_id, context in event_history.items():
        for death in context["deaths"]:
            bounty = death.get("shutdown_bounty") or 0
            if bounty > 0:
                events += 1
                gold += bounty
                matches.add(match_id)

    if events < SHUTDOWN_MIN_EVENTS and gold < SHUTDOWN_MIN_GOLD:
        return []

    return [
        {
            "key": "shutdown_conceded",
            "severity": "warn",
            "title": "제압골 헌납 반복",
            "description": (
                f"최근 경기에서 제압골을 {events}회, 총 {gold}골드 헌납했습니다. "
                "성장 중 데스에서 상대에게 큰 골드가 넘어간 장면이 반복 관측됩니다."
            ),
            "stat": f"{events}회 / {gold}골드",
            "matches": sorted(matches),
        }
    ]


def _chronic_metrics(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []

    for metric_key, threshold, comparator, severity, title, template in CHRONIC_WEAKNESS_RULES:
        avg, matches = _metric_average(records, metric_key)
        if avg is None or len(matches) < 3:
            continue
        if (comparator == "gte" and avg >= threshold) or (comparator == "lte" and avg <= threshold):
            patterns.append(
                {
                    "key": metric_key,
                    "severity": severity,
                    "title": title,
                    "description": template.format(avg=avg),
                    "stat": f"평균 {avg:.0f}점 · 표본 {len(matches)}판",
                    "matches": matches,
                }
            )

    for metric_key, threshold, comparator, title, template in CHRONIC_STRENGTH_RULES:
        avg, matches = _metric_average(records, metric_key)
        if avg is None or len(matches) < 3:
            continue
        if (comparator == "gte" and avg >= threshold) or (comparator == "lte" and avg <= threshold):
            patterns.append(
                {
                    "key": f"strength.{metric_key}",
                    "severity": "positive",
                    "title": title,
                    "description": template.format(avg=avg),
                    "stat": f"평균 {avg:.0f}점 · 표본 {len(matches)}판",
                    "matches": matches,
                }
            )

    return patterns


def _metric_average(
    records: list[dict[str, Any]],
    metric_key: str,
) -> tuple[float | None, list[str]]:
    values: list[float] = []
    matches: list[str] = []
    for record in records:
        value = record.get("scores", {}).get(metric_key)
        if value is None:
            continue
        values.append(float(value))
        matches.append(record["match_id"])
    if not values:
        return None, []
    return sum(values) / len(values), matches


def _objective_after(enemy_objectives: list[dict[str, Any]], death_timestamp_ms: int) -> bool:
    return any(
        death_timestamp_ms <= objective["timestamp_ms"] <= death_timestamp_ms + OBJECTIVE_WINDOW_MS
        for objective in enemy_objectives
    )
