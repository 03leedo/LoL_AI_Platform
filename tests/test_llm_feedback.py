import unittest

from app.services.llm_feedback import _feedback_payload, _merge_llm_feedback


class LlmFeedbackTest(unittest.TestCase):
    def test_merge_llm_feedback_prepends_ai_insight_and_keeps_rule_fallback(self) -> None:
        analysis = {
            "player": {"champion": "Ahri"},
            "scores": {},
            "evidence": [
                {
                    "minute": 12,
                    "type": "objective_setup",
                    "title": "Dragon setup",
                    "description": "Dragon was lost after deaths.",
                    "confidence": "medium",
                    "context": {
                        "summary": {},
                        "insights": [
                            {
                                "tone": "risk",
                                "title": "규칙 기반 시야 코멘트",
                                "description": "상대 와드 이벤트가 더 많았습니다.",
                            }
                        ],
                        "events": [],
                        "snapshots": [],
                    },
                }
            ],
        }
        feedback = {
            "items": [
                {
                    "evidence_index": 0,
                    "insights": [
                        {
                            "tone": "risk",
                            "title": "한타 이후 용 손실",
                            "description": "킬 로그가 먼저 몰린 뒤 용 손실이 이어져 교전 결과가 더 큰 근거에 가깝습니다.",
                        }
                    ],
                }
            ]
        }

        enriched = _merge_llm_feedback(analysis=analysis, feedback=feedback)
        insights = enriched["evidence"][0]["context"]["insights"]

        self.assertEqual(insights[0]["source"], "llm")
        self.assertEqual(insights[0]["title"], "한타 이후 용 손실")
        self.assertEqual(insights[1]["source"], "rules")

    def test_feedback_payload_uses_compact_snapshots(self) -> None:
        analysis = {
            "player": {"champion": "Ahri"},
            "scores": {},
            "evidence": [
                {
                    "minute": 8,
                    "type": "death_cost",
                    "title": "Death cost",
                    "description": "Death was costly.",
                    "confidence": "medium",
                    "context": {
                        "summary": {"ally_deaths": 1},
                        "insights": [],
                        "events": [
                            {
                                "timestamp_ms": 480_000,
                                "type": "kill",
                                "title": "LeeSin -> Ahri",
                                "description": "레드 팀 킬",
                                "team": "red",
                                "victim_team": "blue",
                                "position_x": 7200,
                                "position_y": 7600,
                            }
                        ],
                        "snapshots": [
                            {
                                "timestamp_ms": 420_000,
                                "offset_seconds": -60,
                                "objective_state": {"blue_dragons": 0, "red_dragons": 0},
                                "participants": [],
                            },
                            {
                                "timestamp_ms": 480_000,
                                "offset_seconds": 0,
                                "objective_state": {"blue_dragons": 0, "red_dragons": 0},
                                "participants": [],
                            },
                            {
                                "timestamp_ms": 540_000,
                                "offset_seconds": 60,
                                "objective_state": {"blue_dragons": 0, "red_dragons": 1},
                                "participants": [],
                            },
                            {
                                "timestamp_ms": 600_000,
                                "offset_seconds": 120,
                                "objective_state": {"blue_dragons": 0, "red_dragons": 1},
                                "participants": [],
                            },
                        ],
                        "anchor_timestamp_ms": 480_000,
                    },
                }
            ],
        }

        payload = _feedback_payload(analysis)

        self.assertEqual(len(payload["items"]), 1)
        self.assertLessEqual(len(payload["items"][0]["snapshots"]), 3)
        self.assertEqual(payload["items"][0]["events"][0]["position"], {"x": 7200, "y": 7600})


if __name__ == "__main__":
    unittest.main()
