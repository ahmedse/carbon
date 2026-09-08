"""people/civil_id.py — Kuwait Civil ID validation (Nibras People & Payroll).

Kuwait Civil ID (PACI — Public Authority for Civil Information) is a
12-digit identifier. This module validates:

  1. **Format** — exactly 12 digits (strip optional spaces). This is safe,
     unambiguous, and enforced at write time.
  2. **Check digit** — the 12th digit is a weighted mod-11 checksum over the
     first 11 digits using the PACI weights ``[2,1,6,3,7,9,10,5,8,4,2]``.

RULE_16 (no fabrication): the check-digit algorithm below is implemented from
the widely-documented PACI scheme but is **NOT yet verified against an
authoritative PACI/GOSI dataset** in this repo. Until that verification is
done it is treated as a **warning** (non-blocking), never a hard error. Flip
``ENFORCE_CHECK_DIGIT`` to ``True`` only after backfilling and confirming real
Civil IDs pass (see docs/DESIGN-EMPLOYEE-ONBOARDING-WIZARD.md §6).

Source to confirm before promotion:
  - PACI Civil ID structure & checksum spec (Kuwait), GOSI employee records.
"""
from __future__ import annotations

import re
from typing import List, Tuple

__all__ = [
    'CIVIL_ID_RE',
    'PACI_WEIGHTS',
    'ENFORCE_CHECK_DIGIT',
    'normalize',
    'validate_format',
    'check_digit_valid',
    'validate',
]

# 12 digits, optional internal spaces (UI masks as ``#### #### ####``).
CIVIL_ID_RE = re.compile(r'^\d{12}$')

# PACI check-digit weights over digits 1..11 (0-indexed 0..10).
# Source: PACI Civil ID checksum — CONFIRM against authoritative spec (RULE_16).
PACI_WEIGHTS = (2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)

# False = format-only enforcement (safe). Flip to True after PACI backfill
# verification to also reject bad check digits at write time.
ENFORCE_CHECK_DIGIT = False


def normalize(value: str) -> str:
    """Strip surrounding whitespace and internal spaces (mask ``#### #### ####``)."""
    return (value or '').replace(' ', '').strip()


def validate_format(value: str) -> bool:
    """Return True if ``value`` is exactly 12 digits (spaces ignored)."""
    return bool(CIVIL_ID_RE.match(normalize(value)))


def check_digit_valid(value: str) -> bool:
    """Validate the PACI weighted mod-11 check digit.

    ``value`` must already pass :func:`validate_format` (12 digits). Returns
    False if the checksum does not match; True otherwise. Maps a computed
    check value of 10 to 0 (PACI convention).
    """
    digits = normalize(value)
    if len(digits) != 12 or not digits.isdigit():
        return False
    total = 0
    for i in range(11):
        total += int(digits[i]) * PACI_WEIGHTS[i]
    check = (11 - (total % 11)) % 11
    if check == 10:
        check = 0
    return check == int(digits[11])


def validate(value: str, *, enforce_check_digit: bool | None = None) -> Tuple[bool, List[str]]:
    """Validate a Civil ID string.

    Returns ``(valid, errors)`` where ``errors`` is a list of human-readable
    messages (empty when valid). ``enforce_check_digit`` overrides the module
    default (used by tests to exercise the checksum path).
    """
    if enforce_check_digit is None:
        enforce_check_digit = ENFORCE_CHECK_DIGIT

    raw = (value or '').strip()
    errors: List[str] = []

    if raw == '':
        return True, errors  # optional field

    if not validate_format(raw):
        errors.append('Civil ID must be exactly 12 digits (e.g. 289121300456)')
        return False, errors

    if enforce_check_digit and not check_digit_valid(raw):
        errors.append('Civil ID check digit is invalid (PACI mod-11)')

    return not errors, errors
