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
