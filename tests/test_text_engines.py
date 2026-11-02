import os
import unittest
from types import SimpleNamespace
from unittest import mock

from src import claude_service, config, groq_text_service, text_refiner


def _fake_groq(calls, content):
    class Completions:
        def create(self, **kw):
            calls.append(kw)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    class FakeClient:
        def __init__(self, api_key):
            self.chat = SimpleNamespace(completions=Completions())

    class Err(Exception):
        pass

    return SimpleNamespace(Groq=FakeClient, AuthenticationError=Err, RateLimitError=Err, APIStatusError=Err, APIConnectionError=Err)


class EngineTests(unittest.TestCase):
    def test_groq_is_default_engine(self):
        with mock.patch.dict(os.environ, {"TEXT_ENGINE": ""}), mock.patch.object(config, "_streamlit_secret", return_value=None):
            self.assertEqual(text_refiner.default_engine(), text_refiner.ENGINE_GROQ)
        self.assertEqual(text_refiner.ENGINE_ORDER[0], text_refiner.ENGINE_GROQ)

    def test_text_engine_setting_selects_claude(self):
        with mock.patch.dict(os.environ, {"TEXT_ENGINE": "claude"}):
            self.assertEqual(text_refiner.default_engine(), text_refiner.ENGINE_CLAUDE)

    def test_groq_refine_call_shape(self):
        calls = []
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "k", "GROQ_TEXT_MODEL": ""}), mock.patch.dict("sys.modules", {"groq": _fake_groq(calls, " بكرة ")}):
            text, engine = text_refiner.refine_to_egyptian("غدا", text_refiner.ENGINE_GROQ)
        self.assertEqual((text, engine), ("بكرة", text_refiner.ENGINE_GROQ))
        self.assertEqual(calls[0]["model"], "llama-3.3-70b-versatile")
        self.assertIn("max_completion_tokens", calls[0])
        self.assertEqual(calls[0]["messages"][0]["role"], "system")

    def test_groq_missing_key(self):
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": ""}), mock.patch.object(config, "_streamlit_secret", return_value=None):
            with self.assertRaises(text_refiner.RefineError):
                text_refiner.write_message("brief", text_refiner.ENGINE_GROQ)

    def test_claude_engine_routes_to_claude(self):
        with mock.patch.object(claude_service, "write_message", return_value="x") as m:
            self.assertEqual(text_refiner.write_message("b", text_refiner.ENGINE_CLAUDE), ("x", text_refiner.ENGINE_CLAUDE))
        m.assert_called_once_with("b")

    def test_ollama_cannot_write(self):
        with self.assertRaises(text_refiner.RefineError):
            text_refiner.write_message("b", text_refiner.ENGINE_OLLAMA)

    def test_engine_ready_messages_hide_values(self):
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "secret-value", "ANTHROPIC_API_KEY": ""}), mock.patch.object(config, "_streamlit_secret", return_value=None):
            ok, msg = text_refiner.engine_ready(text_refiner.ENGINE_GROQ)
            self.assertTrue(ok); self.assertNotIn("secret-value", msg)
            ok, msg = text_refiner.engine_ready(text_refiner.ENGINE_CLAUDE)
            self.assertFalse(ok); self.assertIn("ANTHROPIC_API_KEY", msg)


if __name__ == "__main__":
    unittest.main()
