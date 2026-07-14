import unittest

from app.services.analysis_semantics import apply_analysis_semantics


def make_analysis() -> dict:
    return {
        "match_id": "KR_1",
        "player": {"puuid": "p", "team": "blue"},
        "scores": {
            "death_cost_index": {"value": 24, "confidence": "medium", "direction": "higher_is_worse"},
            "objective_setup_score": {"value": 62, "confidence": "medium", "direction": "higher_is_better"},
            "gambler_index": {"value": 40, "confidence": "medium", "direction": "higher_is_worse"},
            "teamfight_persistence_score": {"value": 55, "confidence": "low", "direction": "higher_is_better"},
        },
        "evidence": [
            {
                "minute": 16,
                "type": "death_cost",
                "title": "Death was followed by objective loss",
                "description": "Within 90 seconds of this death, the opposing team secured Dragon.",
                "confidence": "medium",
            },
            {
                "minute": 21,
                "type": "gambler",
                "title": "Isolated death away from allies",
                "description": "Nearest ally was about 5200 units away (frame-based estimate).",
                "confidence": "medium",
            },
            {
                "minute": 0,
                "type": "throw_index",
                "title": "No clear throw pattern detected",
                "description": "The model did not find a death that clearly converted a team lead into a major loss.",
                "confidence": "medium",
            },
        ],
    }


class AnalysisSemanticsTest(unittest.TestCase):
    def test_evidence_ids_are_deterministic_and_unique(self) -> None:
        first = apply_analysis_semantics(make_analysis())
        second = apply_analysis_semantics(make_analysis())

        ids_first = [e["id"] for e in first["evidence"]]
        ids_second = [e["id"] for e in second["evidence"]]

        self.assertEqual(ids_first, ids_second)
        self.assertEqual(len(ids_first), len(set(ids_first)))
        self.assertTrue(all(i.startswith("ev:KR_1:") for i in ids_first))

    def test_score_groups_separate_performance_from_risk_style(self) -> None:
        analysis = apply_analysis_semantics(make_analysis())
        scores = analysis["scores"]

        self.assertEqual(scores["objective_setup_score"]["group"], "performance")
        self.assertEqual(scores["teamfight_persistence_score"]["group"], "performance")
        self.assertEqual(scores["death_cost_index"]["group"], "risk_style")
        self.assertEqual(scores["gambler_index"]["group"], "risk_style")

    def test_observations_reference_existing_evidence(self) -> None:
        analysis = apply_analysis_semantics(make_analysis())
        evidence_ids = {e["id"] for e in analysis["evidence"]}

        observations = [s for s in analysis["statements"] if s["kind"] == "observation"]
        self.assertTrue(observations)
        for statement in observations:
            self.assertTrue(statement["evidence_ids"])
            for evidence_id in statement["evidence_ids"]:
                self.assertIn(evidence_id, evidence_ids)

    def test_neutral_placeholder_evidence_produces_no_observation(self) -> None:
        analysis = apply_analysis_semantics(make_analysis())
        texts = [s["text"] for s in analysis["statements"] if s["kind"] == "observation"]

        self.assertFalse(any("No clear throw pattern" in t for t in texts))

    def test_limitations_include_standard_and_low_confidence_notes(self) -> None:
        analysis = apply_analysis_semantics(make_analysis())
        limitations = [s["text"] for s in analysis["statements"] if s["kind"] == "limitation"]

        self.assertTrue(any("1분 단위" in t for t in limitations))
        # teamfight_persistence_score has low confidence → dedicated limitation
        self.assertTrue(any("teamfight_persistence_score" in t for t in limitations))

    def test_metric_group_registry_covers_all_nine_metrics(self) -> None:
        from app.services.analysis_semantics import PERFORMANCE_METRICS, RISK_STYLE_METRICS

        known = {
            "death_cost_index",
            "throw_index",
            "objective_setup_score",
            "lead_conversion_score",
            "stability_score",
            "gold_retention_score",
            "gambler_index",
            "teamfight_persistence_score",
            "death_acceleration_index",
        }
        self.assertEqual(PERFORMANCE_METRICS | RISK_STYLE_METRICS, known)
        self.assertFalse(PERFORMANCE_METRICS & RISK_STYLE_METRICS)

    def test_unregistered_metric_falls_back_by_direction(self) -> None:
        analysis = make_analysis()
        analysis["scores"]["future_risk_signal"] = {
            "value": 10, "confidence": "low", "direction": "higher_is_worse",
        }
        analysis["scores"]["future_perf_metric"] = {
            "value": 10, "confidence": "low", "direction": "higher_is_better",
        }

        scores = apply_analysis_semantics(analysis)["scores"]

        self.assertEqual(scores["future_risk_signal"]["group"], "risk_style")
        self.assertEqual(scores["future_perf_metric"]["group"], "performance")

    def test_unscored_metric_produces_a_limitation(self) -> None:
        analysis = make_analysis()
        analysis["scores"]["lead_conversion_score"] = {
            "value": None, "confidence": "low", "direction": "higher_is_better",
        }

        limitations = [
            s["text"]
            for s in apply_analysis_semantics(analysis)["statements"]
            if s["kind"] == "limitation"
        ]

        self.assertTrue(any("lead_conversion_score" in t and "산정되지 않았습니다" in t for t in limitations))

    def test_replay_questions_come_from_replay_worthy_evidence(self) -> None:
        analysis = apply_analysis_semantics(make_analysis())
        questions = [s for s in analysis["statements"] if s["kind"] == "replay_question"]

        self.assertEqual(len(questions), 2)  # minute 16 (death_cost) + minute 21 (gambler)
        minutes_in_text = [q["text"][:4] for q in questions]
        self.assertTrue(any("16분" in q["text"] for q in questions))
        self.assertTrue(any("21분" in q["text"] for q in questions))
        for question in questions:
            self.assertTrue(question["evidence_ids"])


if __name__ == "__main__":
    unittest.main()
