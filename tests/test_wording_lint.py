"""Domain-invariant wording lint (Phase 1).

Runs the real metric/pattern generators over fixtures and asserts that no
emitted user-facing text contains causal or judgmental phrasing. "After" must
never become "because of" (CLAUDE.md Domain Invariants #2).
"""

import unittest

from app.services.habit_metrics import merge_habit_metrics
from app.services.patterns import (
    CHRONIC_STRENGTH_RULES,
    CHRONIC_WEAKNESS_RULES,
    detect_patterns,
)
from tests.test_habit_metrics import (
    base_analysis,
    make_feature,
    make_kill,
    make_match,
    make_timeline,
)

FORBIDDEN_PHRASES = [
    # Korean causal / judgmental phrasing
    "때문에",
    "로 인해",
    "만들고 있",
    "무너지",
    "복구시키",
    "문제다",
    "잘못된 판단",
    "일부러",
    # English causal / counterfactual phrasing
    "caused",
    "because of",
    "would have",
    "usually mean",
    "led to the loss",
    # phrases removed in the Phase 1 wording pass — keep them un-revertable
    "delays the snowball",
    "cashing out",
    "스노우볼이 멈추",
    "paying off",
]


def collect_texts_from_analysis(analysis: dict) -> list[str]:
    texts: list[str] = []
    for item in analysis.get("evidence", []):
        texts.append(str(item.get("title") or ""))
        texts.append(str(item.get("description") or ""))
    return texts


class WordingLintTest(unittest.TestCase):
    def assert_clean(self, texts: list[str]) -> None:
        for text in texts:
            lowered = text.lower()
            for phrase in FORBIDDEN_PHRASES:
                self.assertNotIn(
                    phrase.lower(),
                    lowered,
                    msg=f"Causal/judgmental phrase '{phrase}' found in: {text}",
                )

    def test_habit_metric_evidence_language_is_observational(self) -> None:
        # A busy fixture that triggers gold retention, gambler, teamfight, and chains.
        features = [
            make_feature(m, current_gold={1: 2200 if 5 <= m <= 9 else 400})
            for m in range(0, 30)
        ]
        events = [
            make_kill(7 * 60_000, killer=6, victim=1, shutdownBounty=300),
            make_kill(9 * 60_000, killer=7, victim=1, x=12_000, y=12_000),
            make_kill(20 * 60_000, killer=1, victim=6, assistingParticipantIds=[2, 3]),
            make_kill(20 * 60_000 + 5_000, killer=2, victim=7, assistingParticipantIds=[1]),
            make_kill(20 * 60_000 + 10_000, killer=8, victim=1, assistingParticipantIds=[9]),
        ]

        analysis = merge_habit_metrics(base_analysis(), make_match(), make_timeline(events), features)

        self.assert_clean(collect_texts_from_analysis(analysis))

    def test_pattern_language_is_observational(self) -> None:
        records = [
            {
                "match_id": f"KR_{i}",
                "role": "MIDDLE",
                "win": False,
                "scores": {
                    "gold_retention_score": 50,
                    "gambler_index": 50,
                    "death_acceleration_index": 40,
                    "teamfight_persistence_score": 30,
                    "objective_setup_score": 30,
                    "lead_conversion_score": 30,
                    "stability_score": 80,
                },
                "challenges": {},
            }
            for i in range(6)
        ]
        history = {
            f"KR_{i}": {
                "participant_id": 1,
                "team_id": 100,
                "deaths": [
                    {"timestamp_ms": 10 * 60_000, "minute": 10, "x": 11_000, "y": 7_000, "shutdown_bounty": 300}
                ],
                "kills": [],
                "enemy_objectives": [
                    {"timestamp_ms": 10 * 60_000 + 45_000, "minute": 10, "event_type": "ELITE_MONSTER_KILL",
                     "monster_type": "DRAGON", "building_type": None}
                ],
            }
            for i in range(6)
        }

        patterns = detect_patterns(records, history)

        self.assertGreater(len(patterns), 4)  # fixture triggers many rules
        texts = [p["title"] for p in patterns] + [p["description"] for p in patterns]
        self.assert_clean(texts)

    def test_rule_templates_are_clean_at_source(self) -> None:
        texts: list[str] = []
        for rule in CHRONIC_WEAKNESS_RULES:
            texts.extend([rule[4], rule[5]])
        for rule in CHRONIC_STRENGTH_RULES:
            texts.extend([rule[3], rule[4]])
        self.assert_clean(texts)

    def test_service_sources_contain_no_forbidden_phrases(self) -> None:
        # Source-level guard: catches evidence templates in code paths the
        # fixtures above do not exercise (e.g. custom_metrics evidence text).
        import inspect

        from app.services import (
            analysis_semantics,
            custom_metrics,
            habit_metrics,
            patterns,
            reports,
        )

        for module in (analysis_semantics, custom_metrics, habit_metrics, patterns, reports):
            self.assert_clean([inspect.getsource(module)])


if __name__ == "__main__":
    unittest.main()
