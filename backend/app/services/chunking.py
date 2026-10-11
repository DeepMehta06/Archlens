"""Chunking into addressable units.

A chunk is a window of consecutive messages (or sentences for plain text). Every unit
inside a chunk is numbered from 1, so the model cites evidence as chunk id plus unit
numbers and code rebuilds the quote from stored text instead of trusting a copied one.
"""
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.services.whatsapp_parser import ParsedChat

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+")
MAX_PLAIN_UNIT_CHARS = 400


@dataclass
class Unit:
    text: str
    sender: Optional[str] = None
    timestamp_text: Optional[str] = None
    timestamp: Optional[datetime] = None
    message_index: Optional[int] = None
    n: int = 0

    def to_dict(self) -> dict:
        return {
            "n": self.n,
            "text": self.text,
            "sender": self.sender,
            "timestamp_text": self.timestamp_text,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "message_index": self.message_index,
        }

    def render(self) -> str:
        return f"{self.sender}: {self.text}" if self.sender else self.text


@dataclass
class ChunkDraft:
    ordinal: int
    units: list[Unit] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(u.render() for u in self.units)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def first(self) -> Unit:
        return self.units[0]


def units_from_chat(chat: ParsedChat) -> list[Unit]:
    return [
        Unit(
            text=m.text,
            sender=m.sender,
            timestamp_text=m.timestamp_text,
            timestamp=m.timestamp,
            message_index=m.index,
        )
        for m in chat.content_messages
        if m.text.strip()
    ]


def units_from_plain(text: str) -> list[Unit]:
    units: list[Unit] = []
    for paragraph in re.split(r"\n+", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        parts = (
            [paragraph]
            if len(paragraph) <= MAX_PLAIN_UNIT_CHARS
            else _SENTENCE_SPLIT.split(paragraph)
        )
        units.extend(Unit(text=p.strip()) for p in parts if p.strip())
    return units


def chunk_units(units: list[Unit], target_chars: int) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    current = ChunkDraft(ordinal=0)
    size = 0
    for unit in units:
        length = len(unit.render()) + 1
        if current.units and size + length > target_chars:
            chunks.append(current)
            current = ChunkDraft(ordinal=len(chunks))
            size = 0
        unit.n = len(current.units) + 1
        current.units.append(unit)
        size += length
    if current.units:
        chunks.append(current)
    return chunks
