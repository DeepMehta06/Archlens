"""Deterministic evidence verification.

Model output is never trusted for provenance. Quotes are rebuilt from stored units, and
any free-form quote is checked against canonical text after whitespace normalisation.
"""
import re
import unicodedata
from typing import Any, Optional

from app.enums import VerificationStatus

_WHITESPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    return _WHITESPACE.sub(" ", unicodedata.normalize("NFC", text)).strip()


def verify_quote(quote: Optional[str], source_text: str) -> tuple[VerificationStatus, Optional[str]]:
    if not quote or not normalize(quote):
        return VerificationStatus.UNVERIFIED, "No quote was provided."
    if normalize(quote) in normalize(source_text):
        return VerificationStatus.VERIFIED, None
    return VerificationStatus.UNVERIFIED, "Quote was not found in the cited source text."


def resolve_units(
    units: list[dict[str, Any]], numbers: list[int]
) -> tuple[list[dict[str, Any]], list[int]]:
    by_number = {u["n"]: u for u in units}
    valid = [by_number[n] for n in dict.fromkeys(numbers) if n in by_number]
    invalid = [n for n in dict.fromkeys(numbers) if n not in by_number]
    return valid, invalid


def quote_from_units(units: list[dict[str, Any]]) -> str:
    return "\n".join(u["text"] for u in units)


def locate_phrase(phrase: Optional[str], units: list[dict[str, Any]]) -> Optional[str]:
    if not phrase or not normalize(phrase):
        return None
    target = normalize(phrase).casefold()
    for unit in units:
        if target in normalize(unit["text"]).casefold():
            return normalize(phrase)
    return None
