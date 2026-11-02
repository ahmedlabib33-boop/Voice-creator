import os
import unittest
from types import SimpleNamespace
from unittest import mock

from src import claude_service, config, text_refiner


class FakeMessages:
    def __init__(self, calls, response):
        self.calls, self.response = calls, response

    def create(self, **kw):
        self.calls.append(kw)
        return self.response


def _fake_anthropic(calls, response):
    class FakeClient:
        def __init__(self, api_key):
            self.beta = SimpleNamespace(messages=FakeMessages(calls, response))

    class Err(Exception):
        pass

    return SimpleNamespace(
        Anthropic=FakeClient,
        AuthenticationError=Err, RateLimitError=Err, APIStatusError=Err, APIConnectionError=Err,
    )


class ClaudeTests(unittest.TestCase):
    def test_missing_key_is_setup_error(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}), mock.patch.object(config, "_streamlit_secret", return_value=None):
            with self.assertRaises(claude_service.ClaudeSetupError):
                claude_service.refine_to_egyptian("hi")

    def test_refine_uses_opus_and_returns_text(self):
        calls = []
        response = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=" يلا نتكلم بكرة ")])
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k", "CLAUDE_MODEL": "", "CLAUDE_EFFORT": ""}), mock.patch.dict("sys.modules", {"anthropic": _fake_anthropic(calls, response)}):
            out = claude_service.refine_to_egyptian("سنتحدث غدا")
        self.assertEqual(out, "يلا نتكلم بكرة")
        self.assertEqual(calls[0]["model"], "claude-opus-5-5")
        self.assertEqual(calls[0]["fallbacks"], "default")
        self.assertIn("server-side-fallback-2026-07-01", calls[0]["betas"])
        self.assertEqual(calls[0]["output_config"], {"effort": "medium"})
        self.assertIn("سنتحدث غدا", calls[0]["messages"][0]["content"])

    def test_refusal_raises(self):
        response = SimpleNamespace(stop_reason="refusal", stop_details=SimpleNamespace(explanation="nope"), content=[])
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), mock.patch.dict("sys.modules", {"anthropic": _fake_anthropic([], response)}):
            with self.assertRaises(claude_service.ClaudeError):
                claude_service.write_message("brief")

    def test_refiner_prefers_claude(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}), mock.patch.object(claude_service, "refine_to_egyptian", return_value="x") as m:
            text, engine = text_refiner.refine_to_egyptian("y")
        self.assertEqual((text, engine), ("x", text_refiner.ENGINE_CLAUDE))
        m.assert_called_once()

    def test_refiner_falls_back_to_ollama(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}), mock.patch.object(config, "_streamlit_secret", return_value=None), \
             mock.patch.object(text_refiner, "ollama_available", return_value=True), \
             mock.patch.object(text_refiner, "_ollama_refine", return_value="z"):
            self.assertEqual(text_refiner.refine_to_egyptian("y"), ("z", text_refiner.ENGINE_OLLAMA))

    def test_no_engine_message(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}), mock.patch.object(config, "_streamlit_secret", return_value=None), \
             mock.patch.object(text_refiner, "ollama_available", return_value=False):
            with self.assertRaises(text_refiner.RefineError):
                text_refiner.refine_to_egyptian("y")


if __name__ == "__main__":
    unittest.main()
