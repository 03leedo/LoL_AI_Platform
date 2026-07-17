import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.reports import (
    _numbers_in,
    _sanitize_llm_statements,
    build_deterministic_report,
    enrich_report_with_llm,
    get_or_create_report,
)


def make_records(count: int = 6) -> list[dict]:
    return [
        {
            "match_id": f"KR_{i}",
            "role": "MIDDLE",
            "win": i % 2 == 0,
            "scores": {"stability_score": 75, "gold_retention_score": 45},
            "challenges": {"killParticipation": 0.5},
        }
        for i in range(count)
    ]


def make_patterns() -> list[dict]:
    return [
        {
            "key": "gold_retention_score",
            "severity": "warn",
            "title": "킬 골드를 아이템으로 늦게 바꾸는 습관",
            "description": "설명",
            "stat": "평균 45점 · 표본 6판",
            "matches": ["KR_0"],
        },
        {
            "key": "strength.stability_score",
            "severity": "positive",
            "title": "안정적인 데스 관리",
            "description": "설명",
            "stat": "평균 75점 · 표본 6판",
            "matches": ["KR_0"],
        },
    ]


class DeterministicReportTest(unittest.TestCase):
    def test_report_composition(self) -> None:
        records = make_records()
        report = build_deterministic_report(
            puuid="p",
            window_key="recent20",
            records=records,
            scorecard={"games": 6, "abilities": {}},
            role_analysis={"roles": [], "recommended": ["MIDDLE"], "caution": None},
            patterns=make_patterns(),
            autopsy={"deaths": 10},
        )

        self.assertEqual(report["generated_by"], "rules")
        self.assertIn("승률 50%", report["summary"])
        self.assertIn("미드", report["summary"])
        self.assertEqual(len(report["weaknesses"]), 1)
        self.assertEqual(len(report["strengths"]), 1)
        # weakness key has a mapped recommendation
        self.assertEqual(len(report["recommendations"]), 1)
        self.assertFalse(report["needs_ingest"])


class SanitizeLlmStatementsTest(unittest.TestCase):
    KNOWN_REFS = {"pat:gold_retention_score", "KR_0"}
    PAYLOAD_NUMBERS = _numbers_in('{"stat": "평균 45점 · 표본 12판", "share": 0.58}')

    def test_valid_statements_pass(self) -> None:
        result = _sanitize_llm_statements(
            {
                "summary": "요약입니다.",
                "observations": [
                    {"text": "골드 리텐션이 평균 45점으로 관측됩니다.", "refs": ["pat:gold_retention_score"]}
                ],
                "hypotheses": [{"text": "귀환 판단이 늦을 수 있습니다.", "refs": ["KR_0"]}],
                "practice_suggestions": ["다음 몇 판 동안 킬 이후 귀환 타이밍을 기록해 보세요."],
            },
            self.KNOWN_REFS,
            self.PAYLOAD_NUMBERS,
        )

        self.assertIsNotNone(result)
        self.assertEqual(len(result["observations"]), 1)
        self.assertEqual(len(result["hypotheses"]), 1)

    def test_observation_without_refs_is_dropped(self) -> None:
        result = _sanitize_llm_statements(
            {
                "summary": "요약.",
                "observations": [{"text": "근거 없는 주장.", "refs": []}],
            },
            self.KNOWN_REFS,
            self.PAYLOAD_NUMBERS,
        )
        self.assertEqual(result["observations"], [])

    def test_unknown_ref_is_dropped(self) -> None:
        result = _sanitize_llm_statements(
            {
                "summary": "요약.",
                "observations": [{"text": "평균 45점.", "refs": ["pat:유령패턴"]}],
            },
            self.KNOWN_REFS,
            self.PAYLOAD_NUMBERS,
        )
        self.assertEqual(result["observations"], [])

    def test_hallucinated_number_is_dropped(self) -> None:
        result = _sanitize_llm_statements(
            {
                "summary": "요약.",
                "observations": [
                    {"text": "제압골 912골드를 헌납했습니다.", "refs": ["pat:gold_retention_score"]}
                ],
            },
            self.KNOWN_REFS,
            self.PAYLOAD_NUMBERS,
        )
        self.assertEqual(result["observations"], [])

    def test_ratio_may_be_written_as_percent(self) -> None:
        result = _sanitize_llm_statements(
            {
                "summary": "요약.",
                "observations": [{"text": "동반률 58%로 관측.", "refs": ["KR_0"]}],
            },
            self.KNOWN_REFS,
            self.PAYLOAD_NUMBERS,
        )
        self.assertEqual(len(result["observations"]), 1)

    def test_hypotheses_are_capped_at_three(self) -> None:
        result = _sanitize_llm_statements(
            {
                "summary": "요약.",
                "hypotheses": [{"text": f"가설 {i}.", "refs": []} for i in range(6)],
            },
            self.KNOWN_REFS,
            self.PAYLOAD_NUMBERS,
        )
        self.assertEqual(len(result["hypotheses"]), 3)

    def test_summary_with_unsupported_number_rejects_everything(self) -> None:
        result = _sanitize_llm_statements(
            {"summary": "승률이 87%였습니다.", "observations": []},
            self.KNOWN_REFS,
            self.PAYLOAD_NUMBERS,
        )
        self.assertIsNone(result)


class LlmContractV2Test(unittest.TestCase):
    def _content(self) -> dict:
        return build_deterministic_report(
            puuid="p",
            window_key="recent20",
            records=make_records(),
            scorecard={"games": 6, "abilities": {}},
            role_analysis={"roles": [], "recommended": ["MIDDLE"], "caution": None},
            patterns=make_patterns(),
            autopsy={"deaths": 10},
        )

    def test_insufficient_output_falls_back_to_rules_with_reason(self) -> None:
        content = self._content()
        with patch(
            "app.services.reports.generate_json",
            new=AsyncMock(return_value={"insufficient": True, "reason": "표본 부족"}),
        ):
            merged = asyncio.run(enrich_report_with_llm(content, {}, {}))

        self.assertEqual(merged["generated_by"], "rules")
        self.assertEqual(merged["llm_insufficient_reason"], "표본 부족")
        self.assertEqual(merged["summary"], content["summary"])  # rules summary kept

    def test_rules_own_strengths_even_if_llm_returns_them(self) -> None:
        content = self._content()
        llm_output = {
            "summary": "요약입니다.",
            "observations": [
                {"text": "골드 리텐션 평균 45점 경향이 반복 관측됩니다.", "refs": ["pat:gold_retention_score"]}
            ],
            "hypotheses": [],
            "practice_suggestions": ["다음 몇 판 동안 킬 직후 귀환을 시도하고 결과를 기록해 보세요."],
            "strengths": ["LLM이 덮어쓰려는 강점"],
            "weaknesses": ["LLM이 덮어쓰려는 약점"],
        }
        with patch("app.services.reports.generate_json", new=AsyncMock(return_value=llm_output)):
            merged = asyncio.run(enrich_report_with_llm(content, {}, {}))

        self.assertEqual(merged["generated_by"], "llm")
        self.assertEqual(merged["strengths"], content["strengths"])
        self.assertEqual(merged["weaknesses"], content["weaknesses"])
        self.assertEqual(merged["limitations"], content["limitations"])
        self.assertEqual(len(merged["observations"]), 1)
        self.assertEqual(merged["recommendations"], llm_output["practice_suggestions"])


class GetOrCreateReportTest(unittest.TestCase):
    def test_insufficient_games_short_circuits(self) -> None:
        with patch("app.services.reports.fetch_player_match_records", new=AsyncMock(return_value=make_records(2))):
            report = asyncio.run(get_or_create_report(db=object(), puuid="p", window=20))

        self.assertTrue(report["needs_ingest"])
        self.assertEqual(report["games_analyzed"], 2)
        self.assertEqual(report["patterns"], [])

    def test_cache_hit_returns_cached_content(self) -> None:
        cached_row = SimpleNamespace(content={"puuid": "p", "summary": "캐시된 요약", "generated_by": "rules"})
        with (
            patch("app.services.reports.fetch_player_match_records", new=AsyncMock(return_value=make_records(6))),
            patch("app.services.reports.get_cached_report", new=AsyncMock(return_value=cached_row)),
        ):
            report = asyncio.run(get_or_create_report(db=object(), puuid="p", window=20))

        self.assertTrue(report["cached"])
        self.assertEqual(report["summary"], "캐시된 요약")

    def test_fresh_generation_without_llm(self) -> None:
        with (
            patch("app.services.reports.fetch_player_match_records", new=AsyncMock(return_value=make_records(6))),
            patch("app.services.reports.get_cached_report", new=AsyncMock(return_value=None)),
            patch("app.services.reports.fetch_player_event_history", new=AsyncMock(return_value={})),
            patch("app.services.reports.provider_available", return_value=False),
            patch("app.services.reports.save_report", new=AsyncMock()) as save_mock,
        ):
            report = asyncio.run(get_or_create_report(db=object(), puuid="p", window=20))

        self.assertFalse(report["cached"])
        self.assertEqual(report["generated_by"], "rules")
        self.assertIn("recent20", report["cache_key"])
        self.assertIn("KR_0", report["cache_key"])  # latest match id in key
        save_mock.assert_awaited_once()

    def test_force_bypasses_cache_lookup(self) -> None:
        with (
            patch("app.services.reports.fetch_player_match_records", new=AsyncMock(return_value=make_records(6))),
            patch("app.services.reports.get_cached_report", new=AsyncMock()) as cache_mock,
            patch("app.services.reports.fetch_player_event_history", new=AsyncMock(return_value={})),
            patch("app.services.reports.provider_available", return_value=False),
            patch("app.services.reports.save_report", new=AsyncMock()),
        ):
            asyncio.run(get_or_create_report(db=object(), puuid="p", window=20, force=True))

        cache_mock.assert_not_awaited()

    def test_llm_failure_falls_back_to_rules(self) -> None:
        from app.services.llm_provider import LlmProviderError

        with (
            patch("app.services.reports.fetch_player_match_records", new=AsyncMock(return_value=make_records(6))),
            patch("app.services.reports.get_cached_report", new=AsyncMock(return_value=None)),
            patch("app.services.reports.fetch_player_event_history", new=AsyncMock(return_value={})),
            patch("app.services.reports.provider_available", return_value=True),
            patch(
                "app.services.reports.enrich_report_with_llm",
                new=AsyncMock(side_effect=LlmProviderError("boom")),
            ),
            patch("app.services.reports.save_report", new=AsyncMock()),
        ):
            report = asyncio.run(get_or_create_report(db=object(), puuid="p", window=20))

        self.assertEqual(report["generated_by"], "rules")
        self.assertTrue(report["summary"])


if __name__ == "__main__":
    unittest.main()
