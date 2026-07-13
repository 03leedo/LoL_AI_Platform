import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.reports import (
    _sanitize_llm_report,
    build_deterministic_report,
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


class SanitizeLlmReportTest(unittest.TestCase):
    def test_valid_output_passes(self) -> None:
        result = _sanitize_llm_report(
            {
                "summary": "요약입니다.",
                "strengths": ["강점 1", "강점 2", "강점 3", "강점 4"],
                "weaknesses": ["약점"],
                "recommendations": ["조언"],
            }
        )
        self.assertIsNotNone(result)
        self.assertEqual(len(result["strengths"]), 3)  # capped

    def test_missing_summary_fails(self) -> None:
        self.assertIsNone(_sanitize_llm_report({"strengths": [], "weaknesses": [], "recommendations": []}))

    def test_non_list_sections_fail(self) -> None:
        self.assertIsNone(
            _sanitize_llm_report({"summary": "s", "strengths": "not-a-list", "weaknesses": [], "recommendations": []})
        )


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
