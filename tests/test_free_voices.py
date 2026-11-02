import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from src import config, edge_tts_service, local_clone_service, tts_service


class EdgeTests(unittest.TestCase):
    def test_edge_is_first_and_default_provider(self):
        self.assertEqual(tts_service.PROVIDER_ORDER[0], tts_service.PROVIDER_EDGE)
        with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "", "GROQ_API_KEY": "", "AZURE_SPEECH_KEY": "", "AZURE_SPEECH_REGION": "", "OPENAI_API_KEY": ""}), \
             mock.patch.object(config, "_streamlit_secret", return_value=None):
            self.assertEqual(tts_service.default_provider(), tts_service.PROVIDER_EDGE)

    def test_synthesize_uses_soft_preset_and_voice(self):
        calls = []

        class FakeCommunicate:
            def __init__(self, text, voice, rate=None, pitch=None):
                calls.append((text, voice, rate, pitch))
            async def save(self, path):
                Path(path).write_bytes(b"mp3")

        fake = SimpleNamespace(Communicate=FakeCommunicate)
        with mock.patch.dict("sys.modules", {"edge_tts": fake}), tempfile.TemporaryDirectory() as tmp:
            out = edge_tts_service.synthesize("أهلا", "", Path(tmp) / "a.mp3")
            self.assertEqual(out.read_bytes(), b"mp3")
            edge_tts_service.synthesize("أهلا", "ar-EG-ShakirNeural", Path(tmp) / "b.mp3", rate_pct=10, pitch_hz=-5)
        self.assertEqual(calls[0], ("أهلا", "ar-EG-SalmaNeural", "-6%", "-2Hz"))
        self.assertEqual(calls[1], ("أهلا", "ar-EG-ShakirNeural", "+10%", "-5Hz"))

    def test_empty_output_is_an_error(self):
        class FakeCommunicate:
            def __init__(self, *a, **k): pass
            async def save(self, path): Path(path).write_bytes(b"")
        with mock.patch.dict("sys.modules", {"edge_tts": SimpleNamespace(Communicate=FakeCommunicate)}), tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(edge_tts_service.EdgeError):
                edge_tts_service.synthesize("x", "", Path(tmp) / "a.mp3")


class LocalCloneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(local_clone_service, "VOICES_DIR", Path(self.tmp.name) / "voices")
        self.patch.start()

    def tearDown(self):
        self.patch.stop(); self.tmp.cleanup()

    def _make_sample(self):
        import struct, wave
        p = Path(self.tmp.name) / "in.wav"
        with wave.open(str(p), "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100)
            w.writeframes(struct.pack("<h", 0) * 44100 * 2)
        return p

    def test_prepare_clone_normalizes_and_lists(self):
        with self.assertRaises(local_clone_service.LocalCloneSetupError):
            local_clone_service.prepare_clone("Mona Test", [self._make_sample()])  # license not accepted yet
        info = local_clone_service.prepare_clone("Mona Test", [self._make_sample()], license_ok=True)
        self.assertTrue(local_clone_service.license_accepted())
        self.assertEqual(info["voice_id"], "mona-test")
        self.assertEqual(len(info["samples"]), 1)
        import wave
        with wave.open(info["samples"][0]) as w:
            self.assertEqual((w.getnchannels(), w.getframerate()), (1, 22050))
        self.assertEqual(local_clone_service.list_clones()[0]["name"], "Mona Test")
        local_clone_service.delete_clone("mona-test")
        self.assertEqual(local_clone_service.list_clones(), [])

    def test_prepare_requires_name_and_samples(self):
        with self.assertRaises(ValueError):
            local_clone_service.prepare_clone("", [self._make_sample()], license_ok=True)
        with self.assertRaises(ValueError):
            local_clone_service.prepare_clone("x", [], license_ok=True)

    def test_synthesize_calls_xtts_with_arabic_and_samples(self):
        local_clone_service.prepare_clone("Mona", [self._make_sample()], license_ok=True)
        seen = {}

        class FakeModel:
            def tts_to_file(self, **kw):
                seen.update(kw); Path(kw["file_path"]).write_bytes(b"RIFF")

        with mock.patch.object(local_clone_service, "_load_model", return_value=FakeModel()):
            out = local_clone_service.synthesize_wav("أهلا", "mona", Path(self.tmp.name) / "o.wav")
        self.assertTrue(out.exists())
        self.assertEqual(seen["language"], "ar")
        self.assertEqual(len(seen["speaker_wav"]), 1)

    def test_model_load_refuses_without_license(self):
        with mock.patch.object(local_clone_service, "available", return_value=True):
            with self.assertRaises(local_clone_service.LocalCloneSetupError):
                local_clone_service._load_model()

    def test_unknown_clone_is_setup_error(self):
        with self.assertRaises(local_clone_service.LocalCloneSetupError):
            local_clone_service.synthesize_wav("x", "nobody", Path(self.tmp.name) / "o.wav")

    def test_generate_speech_merges_local_chunks(self):
        import struct, wave
        def fake_wav(text, voice_id, out):
            with wave.open(str(out), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(struct.pack("<h", 0) * 2205)
            return out
        with mock.patch.object(local_clone_service, "synthesize_wav", side_effect=fake_wav):
            out = tts_service.generate_speech("جملة. " * 80, tts_service.PROVIDER_LOCAL_CLONE, "mona", Path(self.tmp.name))
        self.assertTrue(out.suffix == ".mp3" and out.stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
