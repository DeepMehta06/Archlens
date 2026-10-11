"""Ledger extraction with deterministic provenance.

The model cites a chunk id and unit numbers; this module rebuilds every quote from stored
text, verifies it, lowers certainty when a hedge is present, merges duplicates without
losing evidence, and drops items whose evidence cannot be resolved. Items always enter
the ledger as ``needs_review`` regardless of what the model says.
"""
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    EvidenceKind,
    EvidenceStatus,
    ItemType,
    QuestionPriority,
    RiskLevel,
    StatedBy,
    VerificationStatus,
)
from app.models import EvidenceLink, LedgerItem, Question, SourceChunk
from app.schemas import ExtractionOutput, LlmItem
from app.services import ledger
from app.services.evidence_verification import (
    locate_phrase,
    quote_from_units,
    resolve_units,
    verify_quote,
)
from app.services.hedging import find_hedges
from app.services.prompts import load_prompt


@dataclass
class ExtractionStats:
    items_created: int = 0
    items_merged: int = 0
    questions_created: int = 0
    hedge_downgrades: int = 0
    dropped_items: list[dict[str, str]] = field(default_factory=list)

    def merge(self, other: "ExtractionStats") -> None:
        self.items_created += other.items_created
        self.items_merged += other.items_merged
        self.questions_created += other.questions_created
        self.hedge_downgrades += other.hedge_downgrades
        self.dropped_items.extend(other.dropped_items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "items_created": self.items_created,
            "items_merged": self.items_merged,
            "questions_created": self.questions_created,
            "hedge_downgrades": self.hedge_downgrades,
            "dropped_items": self.dropped_items,
        }


def roles_for(participants: list[str], me: Optional[str]) -> dict[str, str]:
    if not me:
        return {p: StatedBy.UNKNOWN.value for p in participants}
    return {
        p: (StatedBy.YOU.value if p.casefold() == me.casefold() else StatedBy.CLIENT.value)
        for p in participants
    }


def make_batches(chunks: list[SourceChunk], max_chars: int) -> list[list[SourceChunk]]:
    batches: list[list[SourceChunk]] = []
    current: list[SourceChunk] = []
    size = 0
    for chunk in chunks:
        if current and size + len(chunk.text) > max_chars:
            batches.append(current)
            current, size = [], 0
        current.append(chunk)
        size += len(chunk.text)
    if current:
        batches.append(current)
    return batches


def render_batch(chunks: list[SourceChunk], roles: dict[str, str]) -> str:
    lines: list[str] = []
    if roles:
        described = "; ".join(
            f"{name} = {'you (the freelancer)' if role == 'you' else role}" for name, role in roles.items()
        )
        lines.append(f"PARTICIPANTS: {described}")
    for chunk in chunks:
        lines.append(f"[CHUNK {chunk.id}]")
        for unit in chunk.units_json:
            text = unit["text"].replace("\n", " | ")
            prefix = f"{unit['sender']}: " if unit.get("sender") else ""
            lines.append(f"[{unit['n']}] {prefix}{text}")
    return "\n".join(lines)


async def extract_batch(llm: Any, chunks: list[SourceChunk], roles: dict[str, str]) -> ExtractionOutput:
    messages = [
        {"role": "system", "content": load_prompt("extraction")},
        {"role": "user", "content": render_batch(chunks, roles)},
    ]
    return await llm.chat_json(messages, ExtractionOutput, stage="extraction", temperature=0.1, think=False)


def evidence_speaker(
    senders: list[Optional[str]], roles: dict[str, str]
) -> tuple[Optional[str], StatedBy]:
    known = [(s, roles.get(s, StatedBy.UNKNOWN.value)) for s in senders if s]
    client = next((s for s, r in known if r == StatedBy.CLIENT.value), None)
    if client:
        return client, StatedBy.CLIENT
    if known and all(r == StatedBy.YOU.value for _, r in known):
        return known[0][0], StatedBy.YOU
    return (known[0][0] if known else None), StatedBy.UNKNOWN


def stated_by_from_roles(roles_seen: list[str]) -> StatedBy:
    if StatedBy.CLIENT.value in roles_seen:
        return StatedBy.CLIENT
    if roles_seen and all(r == StatedBy.YOU.value for r in roles_seen):
        return StatedBy.YOU
    return StatedBy.UNKNOWN


def _resolve_evidence(
    item: LlmItem, chunk_by_id: dict[str, SourceChunk], roles: dict[str, str]
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for ev in item.evidence:
        chunk = chunk_by_id.get(ev.chunk_id)
        if chunk is None:
            continue
        units, _ = resolve_units(chunk.units_json, ev.units)
        if not units:
            continue
        if any(verify_quote(u["text"], chunk.text)[0] != VerificationStatus.VERIFIED for u in units):
            continue
        speaker, role = evidence_speaker([u.get("sender") for u in units], roles)
        resolved.append(
            {
                "chunk": chunk,
                "units": units,
                "quote": quote_from_units(units),
                "highlight": locate_phrase(ev.phrase, units),
                "speaker": speaker,
                "role": role.value,
            }
        )
    return resolved


def _evidence_exists(item: LedgerItem, chunk_id: str, numbers: list[int]) -> bool:
    return any(e.chunk_id == chunk_id and sorted(e.unit_numbers or []) == sorted(numbers) for e in item.evidence_links)


async def persist_extraction(
    session: AsyncSession,
    *,
    project_id: str,
    source_id: str,
    chunks: list[SourceChunk],
    output: ExtractionOutput,
    roles: dict[str, str],
    evidence_kind: EvidenceKind = EvidenceKind.TEXT_QUOTE,
) -> ExtractionStats:
    stats = ExtractionStats()
    chunk_by_id = {c.id: c for c in chunks}
    item_by_index: dict[int, LedgerItem] = {}

    for index, candidate in enumerate(output.items):
        evidence = _resolve_evidence(candidate, chunk_by_id, roles)
        if not evidence:
            stats.dropped_items.append(
                {"title": candidate.title[:120], "reason": "No cited evidence could be verified in the sources."}
            )
            continue

        speaker_roles = [e["role"] for e in evidence]
        status = EvidenceStatus(candidate.evidence_status)
        hedges = sorted({h for e in evidence for h in find_hedges(e["quote"])})
        note: Optional[str] = None
        if hedges:
            note = f"Hedge detected: {', '.join(hedges)}."
            if status == EvidenceStatus.EXPLICIT:
                status = EvidenceStatus.TENTATIVE
                note += " Certainty lowered from explicit to tentative."
                stats.hedge_downgrades += 1

        item_type = ItemType(candidate.item_type)
        existing = await ledger.find_duplicate(session, project_id, item_type, candidate.title)
        if existing is not None:
            target = existing
            stats.items_merged += 1
        else:
            target = await ledger.create_item(
                session,
                project_id,
                item_type=item_type,
                title=candidate.title.strip(),
                description=candidate.description.strip(),
                evidence_status=status,
                risk_level=RiskLevel(candidate.risk_level),
                stated_by=stated_by_from_roles(speaker_roles),
            )
            stats.items_created += 1
        item_by_index[index] = target

        for entry, role in zip(evidence, speaker_roles):
            numbers = [u["n"] for u in entry["units"]]
            if _evidence_exists(target, entry["chunk"].id, numbers):
                continue
            link = EvidenceLink(
                ledger_item_id=target.id,
                source_id=source_id,
                chunk_id=entry["chunk"].id,
                evidence_kind=evidence_kind,
                quote=entry["quote"],
                highlight=entry["highlight"],
                unit_numbers=numbers,
                speaker=entry["speaker"],
                speaker_role=StatedBy(role),
                verification_status=VerificationStatus.VERIFIED,
                verification_note=note,
            )
            session.add(link)
            target.evidence_links.append(link)
        await session.flush()

    existing_questions = {
        " ".join(q.casefold().split())
        for q in (await session.execute(select(Question.question).where(Question.project_id == project_id))).scalars()
    }
    for question in output.questions:
        key = " ".join(question.question.casefold().split())
        if not key or key in existing_questions:
            continue
        linked = item_by_index.get(question.item_index) if question.item_index is not None else None
        session.add(
            Question(
                project_id=project_id,
                ledger_item_id=linked.id if linked else None,
                question=question.question.strip(),
                reason=question.reason.strip(),
                priority=QuestionPriority(question.priority),
            )
        )
        existing_questions.add(key)
        stats.questions_created += 1
    await session.flush()
    return stats
