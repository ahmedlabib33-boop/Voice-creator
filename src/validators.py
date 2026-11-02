"""Phone number validation and Egyptian local-number normalization.

Rules:
* ``01xxxxxxxxx`` (11 digits, Egyptian local mobile) -> ``+20`` + digits without the leading 0.
  Example: ``01123040202`` -> ``+201123040202``.
* ``0020...`` international dialing prefix -> ``+20...``.
* ``20...`` (12 digits, country code without plus) -> ``+20...``.
* ``+...`` is accepted as-is when it is valid E.164.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")
EGYPT_MOBILE_RE = re.compile(r"^\+201[0125]\d{8}$")
_STRIP_RE = re.compile(r"[\s\-\(\)\.]")


@dataclass(frozen=True)
class NormalizedPhone:
    original_input: str
    normalized_e164: str

    @property
    def digits(self) -> str:
        """E.164 without the plus sign, as the WhatsApp Cloud API expects."""
        return self.normalized_e164[1:]


def _to_ascii_digits(text: str) -> str:
    """Convert Arabic-Indic digits (٠١٢...) to ASCII so pasted numbers work."""
    out = []
    for ch in text:
        if ch.isdigit():
            out.append(str(int(ch)))
        else:
            out.append(ch)
    return "".join(out)


def normalize_phone(raw: str) -> NormalizedPhone:
    """Normalize user input to E.164. Raises ``ValueError`` with a user-facing message."""
    original = (raw or "").strip()
    if not original:
        raise ValueError("Phone number is required.")

    cleaned = _STRIP_RE.sub("", _to_ascii_digits(original))

    if cleaned.startswith("+"):
        candidate = "+" + re.sub(r"\D", "", cleaned[1:])
    elif cleaned.startswith("00"):
        candidate = "+" + re.sub(r"\D", "", cleaned[2:])
    else:
        digits = re.sub(r"\D", "", cleaned)
        if len(digits) == 11 and digits.startswith("01"):
            candidate = "+20" + digits[1:]
        elif len(digits) == 12 and digits.startswith("201"):
            candidate = "+" + digits
        else:
            raise ValueError(
                "Unrecognized number. Use Egyptian local format 01xxxxxxxxx "
                "or international E.164 format such as +201xxxxxxxxx."
            )

    if not E164_RE.match(candidate):
        raise ValueError(f"'{original}' is not a valid E.164 phone number.")

    return NormalizedPhone(original_input=original, normalized_e164=candidate)


def is_egyptian_mobile(e164: str) -> bool:
    return bool(EGYPT_MOBILE_RE.match(e164 or ""))


def validate_phone_number_id(value: str) -> str:
    """Meta ``phone_number_id`` is a numeric identifier, not a phone number."""
    value = (value or "").strip()
    if not value.isdigit() or len(value) < 10:
        raise ValueError(
            "phone_number_id must be the numeric ID from Meta's WhatsApp Manager, "
            "not the phone number itself."
        )
    return value
