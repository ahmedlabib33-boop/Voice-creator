import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src import config, tts_service
from src.tts_service import GROQ_MAX_CHARS, TTSSetupError, split_text


class SplitTests(unittest.TestCase):
    def test_short_text_single_chunk(self):
        self.assertEqual(split_text("مرحبا", 200), ["مرحبا"])

    def test_chunks_respect_limit_and_keep_all_words(self):
        text = " ".join(f"كلمة{i}" for i in range(300)) + "؟ " + "جملة ثانية. " * 40
        chunks = split_text(text, GROQ_MAX_CHARS)
        self.assertTrue(all(len(c) <= GROQ_MAX_CHARS for c in chunks))
        self.assertEqual(" ".join(chunks).split(), text.split())

    def test_prefers_sentence_boundaries(self):
        chunks = split_text("أهلا بيك. " * 30, 60)
        self.assertTrue(all(c.endswith(".") for c in chunks))

    def test_oversized_token_hard_cut(self):
        chunks = split_text("x" * 450, 200)
        self.assertEqual([len(c) for c in chunks], [200, 200, 50])


class ProviderTests(unittest.TestCase):
    def test_missing_groq_key_raises_setup_error(self):
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": ""}), mock.patch.object(config, "_streamlit_secret", return_value=None):
            with self.assertRaises(TTSSetupError):
                tts_service.generate_speech("hi", tts_service.PROVIDER_GROQ, output_dir=Path(tempfile.mkdtemp()))

    def test_groq_chunks_are_merged_to_mp3(self):
        """Fake the Groq SDK: each chunk writes a silent WAV, then ffmpeg merges to MP3."""
        import struct, wave

        class FakeResponse:
            def write_to_file(self, path):
                with wave.open(str(path), "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                    w.writeframes(struct.pack("<h", 0) * 2400)

        calls = []

        class FakeClient:
            def __init__(self, api_key):
                self.audio = self
                self.speech = self
            def create(self, **kw):
                calls.append(kw)
                return FakeResponse()

        text = "جملة قصيرة. " * 40  # > 200 chars -> several chunks
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}), mock.patch.dict("sys.modules", {"groq": mock.MagicMock(Groq=FakeClient)}):
            out = tts_service.generate_speech(text, tts_service.PROVIDER_GROQ, output_dir=Path(tempfile.mkdtemp()))
        self.assertTrue(out.exists() and out.suffix == ".mp3" and out.stat().st_size > 0)
        self.assertGreater(len(calls), 1)
        self.assertTrue(all(len(c["input"]) <= GROQ_MAX_CHARS and c["response_format"] == "wav" for c in calls))
        self.assertEqual(calls[0]["model"], "canopylabs/orpheus-arabic-saudi")
        self.assertEqual(calls[0]["voice"], "noura")

    def test_default_provider_falls_through_when_no_keys(self):
        with mock.patch.dict(os.environ, {"GROQ_API_KEY": "", "OPENAI_API_KEY": "", "AZURE_SPEECH_KEY": "", "AZURE_SPEECH_REGION": ""}), mock.patch.object(config, "_streamlit_secret", return_value=None):
            statuses = tts_service.provider_statuses()
        keyed = {s.name: s.ready for s in statuses}
        self.assertEqual([keyed[tts_service.PROVIDER_GROQ], keyed[tts_service.PROVIDER_OPENAI], keyed[tts_service.PROVIDER_AZURE]], [False, False, False])
        self.assertNotIn("test", "".join(s.message for s in statuses))


if __name__ == "__main__":
    unittest.main()
