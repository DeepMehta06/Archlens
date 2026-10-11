"""Hedge detection for English, Hinglish and Hindi.

A heuristic cross-check on the model's certainty labels, never the only classifier:
a statement that contains a hedge cannot stay ``explicit``.
"""
import re

LATIN_HEDGES = (
    "maybe", "perhaps", "not sure", "unsure", "not certain", "might", "possibly", "probably",
    "tbd", "i think", "we'll see", "we will see", "let's see", "if possible", "depends",
    "shayad", "pakka nahi", "pakka nhi", "pata nahi", "pata nhi", "baad me", "baad mein",
    "dekhte hain", "dekhenge", "ho sakta hai", "lagta hai", "confirm nahi", "sochna padega",
    "abhi nahi pata", "nahi pata",
)
DEVANAGARI_HEDGES = (
    "शायद",
    "पक्का नहीं",
    "पता नहीं",
    "बाद में",
    "देखते हैं",
    "हो सकता है",
)

_LATIN_PATTERNS = [
    (term, re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, term.split())) + r"(?!\w)", re.IGNORECASE))
    for term in LATIN_HEDGES
]


def find_hedges(text: str) -> list[str]:
    found = [term for term, pattern in _LATIN_PATTERNS if pattern.search(text)]
    found.extend(term for term in DEVANAGARI_HEDGES if term in text)
    return found
