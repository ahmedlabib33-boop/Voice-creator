import unittest

from src.validators import is_egyptian_mobile, normalize_phone, validate_phone_number_id


class NormalizeTests(unittest.TestCase):
    def test_egyptian_local(self):
        n = normalize_phone("01123040202")
        self.assertEqual(n.normalized_e164, "+201123040202")
        self.assertEqual(n.original_input, "01123040202")
        self.assertEqual(n.digits, "201123040202")

    def test_double_zero_prefix(self):
        self.assertEqual(normalize_phone("00201123040202").normalized_e164, "+201123040202")

    def test_country_code_without_plus(self):
        self.assertEqual(normalize_phone("201123040202").normalized_e164, "+201123040202")

    def test_e164_unchanged(self):
        self.assertEqual(normalize_phone("+201123040202").normalized_e164, "+201123040202")

    def test_spaces_and_dashes(self):
        self.assertEqual(normalize_phone("0112 304-0202").normalized_e164, "+201123040202")

    def test_arabic_indic_digits(self):
        self.assertEqual(normalize_phone("٠١١٢٣٠٤٠٢٠٢").normalized_e164, "+201123040202")

    def test_non_egyptian_e164(self):
        self.assertEqual(normalize_phone("+14155552671").normalized_e164, "+14155552671")

    def test_rejects_garbage(self):
        for bad in ("", "abc", "123", "0211230402", "011230402020"):
            with self.assertRaises(ValueError):
                normalize_phone(bad)

    def test_is_egyptian_mobile(self):
        self.assertTrue(is_egyptian_mobile("+201123040202"))
        self.assertFalse(is_egyptian_mobile("+14155552671"))

    def test_phone_number_id(self):
        self.assertEqual(validate_phone_number_id(" 123456789012345 "), "123456789012345")
        with self.assertRaises(ValueError):
            validate_phone_number_id("+201123040202")


if __name__ == "__main__":
    unittest.main()


class KeysFileTests(unittest.TestCase):
    def test_keys_txt_applies_only_non_blank_values(self):
        import os, tempfile
        from pathlib import Path
        from unittest import mock
        from src import config

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keys.txt"
            path.write_text("﻿# comment\nANTHROPIC_API_KEY= sk-test \nGROQ_API_KEY=\nbad line\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"GROQ_API_KEY": "keep"}):
                self.assertEqual(config.load_keys_file(path), 1)
                self.assertEqual(os.environ["ANTHROPIC_API_KEY"], "sk-test")
                self.assertEqual(os.environ["GROQ_API_KEY"], "keep")

    def test_lenient_formats(self):
        from src.config import parse_keys_text
        text = "Claude API: sk-ant-abc\ngroq = gsk_xyz\nsk-proj-123\nWHATSAPP_ACCESS_TOKEN=EAAB\nnot a key\n"
        parsed = parse_keys_text(text)
        self.assertEqual(parsed["ANTHROPIC_API_KEY"], "sk-ant-abc")
        self.assertEqual(parsed["GROQ_API_KEY"], "gsk_xyz")
        self.assertEqual(parsed["OPENAI_API_KEY"], "sk-proj-123")
        self.assertEqual(parsed["WHATSAPP_ACCESS_TOKEN"], "EAAB")
        self.assertNotIn("NOT A KEY", parsed)

    def test_finds_api_keys_file_in_parent_folder(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        from src import config

        with tempfile.TemporaryDirectory() as tmp:
            parent = Path(tmp); app = parent / "Voice-creator"; app.mkdir()
            (parent / "API keys.txt").write_text("groq: gsk_1\n", encoding="utf-8")
            with mock.patch.object(config, "APP_DIR", app):
                self.assertEqual(config.find_keys_file(), parent / "API keys.txt")
