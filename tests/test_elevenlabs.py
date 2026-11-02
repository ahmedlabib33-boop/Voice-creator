import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from src import config, elevenlabs_service, tts_service


def _resp(status=200, json_data=None, content=b""):
    r = SimpleNamespace(status_code=status, content=content, text="")
    r.json = lambda: json_data if json_data is not None else {}
    return r


class ElevenLabsTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "k", "ELEVENLABS_MODEL": "", "ELEVENLABS_VOICE_ID": ""})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_synthesize_posts_to_tts_endpoint(self):
        calls = []
        def fake_post(url, **kw):
            calls.append((url, kw)); return _resp(200, content=b"ID3mp3")
        with mock.patch.object(elevenlabs_service.requests, "post", fake_post), tempfile.TemporaryDirectory() as tmp:
            out = elevenlabs_service.synthesize("أهلا", "voice123", Path(tmp) / "a.mp3")
            self.assertEqual(out.read_bytes(), b"ID3mp3")
        url, kw = calls[0]
        self.assertTrue(url.endswith("/v1/text-to-speech/voice123"))
        self.assertEqual(kw["headers"]["xi-api-key"], "k")
        self.assertEqual(kw["params"]["output_format"], "mp3_44100_128")
        self.assertEqual(kw["json"]["model_id"], "eleven_multilingual_v2")
        self.assertIn("stability", kw["json"]["voice_settings"])

    def test_401_gives_clear_error(self):
        with mock.patch.object(elevenlabs_service.requests, "post", lambda *a, **k: _resp(401, {"detail": {"status": "x"}})):
            with self.assertRaises(elevenlabs_service.ElevenLabsError) as ctx:
                elevenlabs_service.synthesize("x", "v", Path(tempfile.mkdtemp()) / "a.mp3")
        self.assertIn("ELEVENLABS_API_KEY", str(ctx.exception))

    def test_list_voices_paginates_and_ranks_clones_and_female_first(self):
        pages = [
            _resp(200, {"voices": [{"voice_id": "m", "name": "Adam", "category": "premade", "labels": {"gender": "male"}}], "has_more": True, "next_page_token": "t2"}),
            _resp(200, {"voices": [{"voice_id": "f", "name": "Sara", "category": "premade", "labels": {"gender": "female", "accent": "Arabic"}},
                                   {"voice_id": "c", "name": "Mona", "category": "cloned", "labels": {}}], "has_more": False}),
        ]
        with mock.patch.object(elevenlabs_service.requests, "get", lambda *a, **k: pages.pop(0)):
            voices = elevenlabs_service.list_voices()
        self.assertEqual([v.voice_id for v in voices], ["c", "f", "m"])
        self.assertEqual(voices[1].label, "Sara · female, Arabic")

    def test_clone_sends_multipart_and_returns_result(self):
        calls = []
        def fake_post(url, **kw):
            calls.append((url, kw)); return _resp(200, {"voice_id": "new1", "requires_verification": False})
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(elevenlabs_service.requests, "post", fake_post):
            sample = Path(tmp) / "s.mp3"; sample.write_bytes(b"abc")
            result = elevenlabs_service.clone_voice("Mona", [sample], labels={"gender": "female"})
        self.assertEqual(result.voice.voice_id, "new1")
        url, kw = calls[0]
        self.assertTrue(url.endswith("/v1/voices/add"))
        self.assertEqual(kw["data"]["name"], "Mona")
        self.assertEqual(kw["data"]["remove_background_noise"], "true")
        self.assertEqual(kw["files"][0][0], "files")

    def test_clone_requires_name_and_samples(self):
        with self.assertRaises(ValueError):
            elevenlabs_service.clone_voice("", [Path("x")])
        with self.assertRaises(ValueError):
            elevenlabs_service.clone_voice("n", [])

    def test_provider_order_and_default(self):
        self.assertEqual(tts_service.PROVIDER_ORDER[0], tts_service.PROVIDER_ELEVENLABS)
        self.assertEqual(tts_service.PROVIDER_ORDER[1], tts_service.PROVIDER_AZURE)
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "", "GROQ_API_KEY": "g", "AZURE_SPEECH_KEY": "", "AZURE_SPEECH_REGION": "", "OPENAI_API_KEY": ""}), \
             mock.patch.object(config, "_streamlit_secret", return_value=None):
            self.assertEqual(tts_service.default_provider(), tts_service.PROVIDER_GROQ)
        self.assertEqual(tts_service.default_provider(), tts_service.PROVIDER_ELEVENLABS)

    def test_generate_speech_routes_options_to_elevenlabs(self):
        seen = {}
        def fake_synth(text, voice_id, output, settings=None, model_id=None):
            seen.update(voice_id=voice_id, settings=settings, model_id=model_id); output.write_bytes(b"x"); return output
        with mock.patch.object(elevenlabs_service, "synthesize", fake_synth), tempfile.TemporaryDirectory() as tmp:
            tts_service.generate_speech("hi", tts_service.PROVIDER_ELEVENLABS, "v9", Path(tmp), {"model_id": "eleven_v4", "settings": {"stability": 0.9}})
        self.assertEqual((seen["voice_id"], seen["model_id"], seen["settings"]["stability"]), ("v9", "eleven_v4", 0.9))


if __name__ == "__main__":
    unittest.main()
