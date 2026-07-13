import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.llm_provider import LlmProviderError, _parse_json, generate_json, provider_available


def fake_settings(**overrides) -> SimpleNamespace:
    base = {
        "llm_provider": "openai",
        "openai_api_key": "",
        "openai_model": "test-model",
        "openai_base_url": "https://api.openai.com/v1",
        "anthropic_api_key": "",
        "anthropic_model": "test-model",
        "anthropic_base_url": "https://api.anthropic.com",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class ParseJsonTest(unittest.TestCase):
    def test_plain_json(self) -> None:
        self.assertEqual(_parse_json('{"a": 1}'), {"a": 1})

    def test_fenced_json(self) -> None:
        text = '```json\n{"summary": "요약"}\n```'
        self.assertEqual(_parse_json(text), {"summary": "요약"})

    def test_invalid_json_raises(self) -> None:
        with self.assertRaises(LlmProviderError):
            _parse_json("not json at all")

    def test_non_object_raises(self) -> None:
        with self.assertRaises(LlmProviderError):
            _parse_json("[1, 2, 3]")


class ProviderSelectionTest(unittest.TestCase):
    def test_provider_unavailable_without_keys(self) -> None:
        with patch("app.services.llm_provider.get_settings", return_value=fake_settings()):
            self.assertFalse(provider_available())

    def test_openai_key_enables_default_provider(self) -> None:
        with patch("app.services.llm_provider.get_settings", return_value=fake_settings(openai_api_key="key")):
            self.assertTrue(provider_available())

    def test_anthropic_provider_requires_anthropic_key(self) -> None:
        with patch(
            "app.services.llm_provider.get_settings",
            return_value=fake_settings(llm_provider="anthropic", openai_api_key="key"),
        ):
            self.assertFalse(provider_available())
        with patch(
            "app.services.llm_provider.get_settings",
            return_value=fake_settings(llm_provider="anthropic", anthropic_api_key="key"),
        ):
            self.assertTrue(provider_available())

    def test_generate_json_raises_without_key(self) -> None:
        with patch("app.services.llm_provider.get_settings", return_value=fake_settings()):
            with self.assertRaises(LlmProviderError):
                asyncio.run(generate_json("system", {"a": 1}))


if __name__ == "__main__":
    unittest.main()
