"""Parser for WhatsApp ``.txt`` chat exports.

Handles the Android layout (``12/03/2026, 14:05 - Name: text``) and the iOS layout
(``[12/03/2026, 14:05:33] Name: text``), 12h and 24h clocks, multi-line messages,
system notices and omitted media. Day/month order is inferred from the data and the
ambiguity is reported instead of hidden.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

_LINE_RE = re.compile(
    r"^\[?(?P<d1>\d{1,2})[/.\-](?P<d2>\d{1,2})[/.\-](?P<year>\d{2,4}),?\s+"
    r"(?P<hour>\d{1,2})[:.](?P<minute>\d{2})(?:[:.](?P<second>\d{2}))?"
    r"(?:\s?(?P<meridiem>[AaPp])\.?\s?[Mm]\.?)?\]?\s*(?:-\s*)?(?P<rest>.*)$"
)
_SENDER_RE = re.compile(r"^(?P<sender>[^:\n]{1,80}?):\s(?P<text>.*)$", re.DOTALL)
_MEDIA_RE = re.compile(
    r"^<?\s*(media|image|video|audio|sticker|gif|document|contact card|voice call)\b.*\bomitted\s*>?$",
    re.IGNORECASE,
)
_INVISIBLE = dict.fromkeys(map(ord, "‎‏﻿‪‫‬"), None)


@dataclass
class ParsedMessage:
    index: int
    sender: Optional[str]
    text: str
    timestamp_text: str
    timestamp: Optional[datetime]
    is_system: bool = False
    is_media: bool = False


@dataclass
class ParsedChat:
    messages: list[ParsedMessage]
    participants: list[str]
    day_first: bool
    date_ambiguous: bool
    skipped_system: int = 0
    skipped_media: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def content_messages(self) -> list[ParsedMessage]:
        return [m for m in self.messages if not m.is_system and not m.is_media]


def _clean(text: str) -> str:
    return text.replace(" ", " ").replace(" ", " ").translate(_INVISIBLE)


def _decide_day_first(pairs: list[tuple[int, int]]) -> tuple[bool, bool]:
    if any(a > 12 for a, _ in pairs):
        return True, False
    if any(b > 12 for _, b in pairs):
        return False, False
    return True, True


def _build_timestamp(match: re.Match, day_first: bool) -> Optional[datetime]:
    d1, d2 = int(match["d1"]), int(match["d2"])
    day, month = (d1, d2) if day_first else (d2, d1)
    year = int(match["year"])
    year += 2000 if year < 100 else 0
    hour, minute = int(match["hour"]), int(match["minute"])
    second = int(match["second"]) if match["second"] else 0
    meridiem = (match["meridiem"] or "").lower()
    if meridiem:
        hour = hour % 12 + (12 if meridiem == "p" else 0)
    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None


def parse_whatsapp(raw: str) -> Optional[ParsedChat]:
    lines = [_clean(line.rstrip("\r")) for line in raw.replace("\r\n", "\n").split("\n")]
    nonempty = [line for line in lines if line.strip()]
    if not nonempty:
        return None

    drafts: list[dict] = []
    for line in lines:
        match = _LINE_RE.match(line)
        if match:
            rest = match["rest"]
            sender_match = _SENDER_RE.match(rest)
            drafts.append(
                {
                    "match": match,
                    "sender": sender_match["sender"].strip() if sender_match else None,
                    "text": sender_match["text"] if sender_match else rest,
                    "is_system": sender_match is None,
                }
            )
        elif drafts and line.strip():
            drafts[-1]["text"] += "\n" + line.strip()

    starts = len(drafts)
    if starts < 2 or starts < 0.3 * len(nonempty):
        return None

    day_first, ambiguous = _decide_day_first(
        [(int(d["match"]["d1"]), int(d["match"]["d2"])) for d in drafts]
    )

    messages: list[ParsedMessage] = []
    skipped_system = skipped_media = 0
    for draft in drafts:
        text = draft["text"].strip()
        match = draft["match"]
        timestamp_text = f"{match['d1']}/{match['d2']}/{match['year']}, {match['hour']}:{match['minute']}"
        if match["meridiem"]:
            timestamp_text += f" {match['meridiem'].upper()}M"
        is_media = bool(_MEDIA_RE.match(text))
        skipped_system += draft["is_system"]
        skipped_media += is_media and not draft["is_system"]
        messages.append(
            ParsedMessage(
                index=len(messages),
                sender=draft["sender"],
                text=text,
                timestamp_text=timestamp_text,
                timestamp=_build_timestamp(match, day_first),
                is_system=draft["is_system"],
                is_media=is_media and not draft["is_system"],
            )
        )

    participants = list(dict.fromkeys(m.sender for m in messages if m.sender and not m.is_system))
    if not participants:
        return None
    return ParsedChat(
        messages=messages,
        participants=participants,
        day_first=day_first,
        date_ambiguous=ambiguous,
        skipped_system=skipped_system,
        skipped_media=skipped_media,
    )
