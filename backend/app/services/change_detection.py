"""Change detection: compare an incoming client request against an approved scope snapshot.

The whole baseline goes into the prompt (it is small); hybrid retrieval only supplies older
conversation context. Code validates every cited id, downgrades unsupported verdicts to
``unclear`` and files new requests as ``needs_review`` candidates. The model never approves
scope.
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.enums import (
    ChangeClass,
    EvidenceKind,
    EvidenceStatus,
    ItemType,
    RiskLevel,
    SourceStatus,
    SourceType,
    StatedBy,
    VerificationStatus,
)
from app.models import ChangeReport, EvidenceLink, Project, ScopeSnapshot, Source
from app.schemas import ChangeOutput
from app.services import ledger, lexical_search
from app.services.chunking import chunk_units, units_from_plain
from app.services.evidence_verification import quote_from_units, resolve_units
from app.services.hedging import find_hedges
from app.services.hybrid_retrieval import Retriever
from app.services.prompts import load_prompt
from app.services.source_ingestion import store_chunks

CONTEXT_CHARS = 600


def _normalize_id(value: str) -> str:
    return value.strip().upper().replace("_", "-")


async def compare_request(
    session: AsyncSession,
    *,
    llm: Any,
    retriever: Retriever,
    embedder: Any,
    project: Project,
    snapshot: ScopeSnapshot,
    incoming_text: str,
) -> ChangeReport:
    settings = get_settings()
    source = Source(
        project_id=project.id,
        source_type=SourceType.TEXT,
        label="Incoming request",
        raw_text=incoming_text,
        metadata_json={"kind": "incoming_request", "snapshot_id": snapshot.id},
        status=SourceStatus.PROCESSED,
        processed_at=datetime.now(timezone.utc),
    )
    session.add(source)
    await session.flush()
    drafts = chunk_units(units_from_plain(incoming_text), 10**9)
    chunks = await store_chunks(session, source, drafts)
    await lexical_search.index_chunks(session, chunks)
    vectors = await embedder.embed_documents([c.text for c in chunks])
    if vectors is not None:
        for chunk, vector in zip(chunks, vectors):
            chunk.embedding_json = vector
    incoming_chunk = chunks[0]

    found = await retriever.search_chunks(session, project.id, incoming_text, top_k=5)
    context_hits = [h for h in found.hits if h.source_id != source.id]

    baseline = snapshot.snapshot_json["items"]
    baseline_lines = [
        f"{i['display_id']} [{i['item_type']}|{i['evidence_status']}] {i['title']}: {i['description']}"
        for i in baseline
    ]
    incoming_lines = [f"[{u['n']}] {u['text']}" for u in incoming_chunk.units_json]
    context_lines = [f"[{h.chunk_id}] {h.text[:CONTEXT_CHARS]}" for h in context_hits]
    messages = [
        {"role": "system", "content": load_prompt("change_detection")},
        {
            "role": "user",
            "content": "BASELINE:\n"
            + "\n".join(baseline_lines)
            + "\n\nINCOMING:\n"
            + "\n".join(incoming_lines)
            + "\n\nCONTEXT:\n"
            + ("\n".join(context_lines) or "(none)"),
        },
    ]
    output = await llm.chat_json(messages, ChangeOutput, stage="change_detection", temperature=0.1, think=False)

    id_by_display = {_normalize_id(i["display_id"]): i["id"] for i in baseline}
    support_ids = [incoming_chunk.id] + [h.chunk_id for h in context_hits]
    results: list[dict[str, Any]] = []
    removed_ids = 0

    for change in output.changes:
        related_displays = [_normalize_id(d) for d in change.related_baseline_ids]
        valid_displays = [d for d in related_displays if d in id_by_display]
        removed_ids += len(related_displays) - len(valid_displays)
        classification = ChangeClass(change.classification)
        explanation = change.explanation.strip()

        if classification in (ChangeClass.ALREADY_COVERED, ChangeClass.CONTRADICTION) and not valid_displays:
            explanation = f"No valid baseline item was cited, so this could not be confirmed. {explanation}"
            classification = ChangeClass.UNCLEAR
        if classification == ChangeClass.NEW_REQUIREMENT:
            valid_displays = []

        candidate_id = None
        if classification == ChangeClass.NEW_REQUIREMENT:
            units, _ = resolve_units(incoming_chunk.units_json, change.units)
            if units:
                candidate_id = await _file_candidate(
                    session, project.id, source.id, incoming_chunk.id, change.incoming_claim, units
                )

        results.append(
            {
                "incoming_claim": change.incoming_claim,
                "classification": classification.value,
                "related_baseline_item_ids": [id_by_display[d] for d in valid_displays],
                "related_display_ids": valid_displays,
                "supporting_chunk_ids": support_ids,
                "explanation": explanation,
                "confidence": change.confidence,
                "candidate_item_id": candidate_id,
            }
        )

    report = ChangeReport(
        project_id=project.id,
        source_id=source.id,
        snapshot_id=snapshot.id,
        results_json={
            "results": results,
            "retrieval_mode": found.mode,
            "invalid_ids_removed": removed_ids,
        },
    )
    session.add(report)
    await session.flush()
    return report


async def _file_candidate(
    session: AsyncSession,
    project_id: str,
    source_id: str,
    chunk_id: str,
    claim: str,
    units: list[dict[str, Any]],
) -> str:
    quote = quote_from_units(units)
    hedges = find_hedges(quote)
    title = " ".join(claim.split())[:120]
    item = await ledger.find_duplicate(session, project_id, ItemType.REQUIREMENT, title)
    if item is None:
        item = await ledger.create_item(
            session,
            project_id,
            item_type=ItemType.REQUIREMENT,
            title=title,
            description=claim.strip(),
            evidence_status=EvidenceStatus.TENTATIVE if hedges else EvidenceStatus.EXPLICIT,
            risk_level=RiskLevel.MEDIUM,
            stated_by=StatedBy.CLIENT,
        )
    link = EvidenceLink(
        ledger_item_id=item.id,
        source_id=source_id,
        chunk_id=chunk_id,
        evidence_kind=EvidenceKind.TEXT_QUOTE,
        quote=quote,
        unit_numbers=[u["n"] for u in units],
        speaker=None,
        speaker_role=StatedBy.CLIENT,
        verification_status=VerificationStatus.VERIFIED,
        verification_note="Incoming request." + (f" Hedge detected: {', '.join(hedges)}." if hedges else ""),
    )
    session.add(link)
    item.evidence_links.append(link)
    await session.flush()
    return item.id
