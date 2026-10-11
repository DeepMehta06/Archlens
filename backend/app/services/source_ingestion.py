"""Source ingestion: parse, chunk, embed, index and extract, reporting real stage progress.

The pipeline never reports success it did not achieve: a failure marks the source and the
job failed with a readable message. If embeddings are unavailable the source is still
indexed for BM25 and the job result says retrieval is degraded.
"""
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.enums import JobStatus, SourceStatus, SourceType, StatedBy
from app.logging_config import get_logger
from app.models import EvidenceLink, LedgerItem, Project, Source, SourceChunk
from app.services import lexical_search
from app.services.chunking import ChunkDraft, chunk_units, units_from_chat, units_from_plain
from app.services.embeddings import EmbeddingService
from app.services.extraction import (
    ExtractionStats,
    extract_batch,
    make_batches,
    evidence_speaker,
    persist_extraction,
    roles_for,
    stated_by_from_roles,
)
from app.services.jobs import update_job
from app.services.ollama_client import OllamaBadResponse, OllamaError
from app.services.media_ingestion import MediaError, evidence_kind_for, media_to_text
from app.services.whatsapp_parser import ParsedChat, parse_whatsapp

logger = get_logger(__name__)


def decode_upload(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _chat_metadata(chat: ParsedChat, me: Optional[str]) -> dict[str, Any]:
    return {
        "participants": chat.participants,
        "me": me,
        "needs_me": me is None,
        "day_first": chat.day_first,
        "date_ambiguous": chat.date_ambiguous,
        "skipped_system": chat.skipped_system,
        "skipped_media": chat.skipped_media,
        "message_count": len(chat.content_messages),
    }


async def create_text_source(
    session: AsyncSession,
    project: Project,
    text: str,
    *,
    label: Optional[str] = None,
    me: Optional[str] = None,
    filename: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> Source:
    me = me or project.my_name
    chat = parse_whatsapp(text)
    source = Source(
        project_id=project.id,
        source_type=SourceType.WHATSAPP if chat else SourceType.TEXT,
        label=label or filename or ("WhatsApp chat" if chat else "Pasted text"),
        filename=filename,
        mime_type=mime_type or "text/plain",
        raw_text=text,
        metadata_json=_chat_metadata(chat, me) if chat else {"me": me},
        status=SourceStatus.UPLOADED,
    )
    session.add(source)
    await session.flush()
    return source


async def create_media_source(
    session: AsyncSession,
    project: Project,
    data: bytes,
    *,
    source_type: SourceType,
    filename: str,
    mime_type: Optional[str] = None,
) -> Source:
    settings = get_settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower()
    path = settings.uploads_dir / f"{uuid.uuid4().hex}{suffix}"
    path.write_bytes(data)
    source = Source(
        project_id=project.id,
        source_type=source_type,
        label=filename,
        filename=filename,
        mime_type=mime_type,
        file_path=str(path),
        metadata_json={"me": project.my_name, "transcribed": True},
        status=SourceStatus.UPLOADED,
    )
    session.add(source)
    await session.flush()
    return source


async def apply_me(session: AsyncSession, source: Source, me: str) -> None:
    metadata = dict(source.metadata_json or {})
    participants = metadata.get("participants", [])
    metadata.update({"me": me, "needs_me": False})
    source.metadata_json = metadata
    roles = roles_for(participants, me)

    links = (
        await session.execute(select(EvidenceLink).where(EvidenceLink.source_id == source.id))
    ).scalars().all()
    affected: dict[str, LedgerItem] = {}
    for link in links:
        chunk = await session.get(SourceChunk, link.chunk_id) if link.chunk_id else None
        wanted = set(link.unit_numbers or [])
        senders = [u.get("sender") for u in (chunk.units_json if chunk else []) if u["n"] in wanted]
        link.speaker, link.speaker_role = evidence_speaker(senders, roles)
        affected[link.ledger_item_id] = None
    for item_id in affected:
        item = await session.get(LedgerItem, item_id)
        await session.refresh(item, attribute_names=["evidence_links"])
        item.stated_by = stated_by_from_roles([e.speaker_role.value for e in item.evidence_links])
    await session.flush()


def build_chunk_drafts(source: Source, target_chars: int) -> list[ChunkDraft]:
    chat = parse_whatsapp(source.raw_text or "") if source.source_type == SourceType.WHATSAPP else None
    units = units_from_chat(chat) if chat else units_from_plain(source.raw_text or "")
    return chunk_units(units, target_chars)


async def store_chunks(
    session: AsyncSession, source: Source, drafts: list[ChunkDraft]
) -> list[SourceChunk]:
    rows: list[SourceChunk] = []
    for draft in drafts:
        first = draft.first
        rows.append(
            SourceChunk(
                project_id=source.project_id,
                source_id=source.id,
                ordinal=draft.ordinal,
                text=draft.text,
                content_hash=draft.content_hash,
                units_json=[u.to_dict() for u in draft.units],
                message_index=first.message_index,
                sender=first.sender,
                timestamp_text=first.timestamp_text,
                message_timestamp=first.timestamp,
            )
        )
    session.add_all(rows)
    await session.flush()
    return rows


async def process_source(
    session_factory: async_sessionmaker[AsyncSession],
    llm: Any,
    embedder: EmbeddingService,
    source_id: str,
    job_id: str,
) -> None:
    settings = get_settings()
    try:
        await update_job(session_factory, job_id, status=JobStatus.PROCESSING, stage="reading", progress=5)
        async with session_factory() as session:
            source = await session.get(Source, source_id)
            if source is None:
                raise ValueError("Source not found.")
            source.status = SourceStatus.PROCESSING
            await session.commit()
            source_type = source.source_type
            needs_transcript = source_type in (SourceType.IMAGE, SourceType.AUDIO, SourceType.PDF) and not source.raw_text
            media_path = source.file_path

        if needs_transcript:
            await update_job(session_factory, job_id, stage="transcribing", progress=10)
            transcript, extra = await media_to_text(llm, source_type, Path(media_path))
            async with session_factory() as session:
                source = await session.get(Source, source_id)
                source.raw_text = transcript
                source.metadata_json = {**(source.metadata_json or {}), **extra, "transcript_model": llm.model}
                await session.commit()

        async with session_factory() as session:
            source = await session.get(Source, source_id)
            drafts = build_chunk_drafts(source, settings.CHUNK_TARGET_CHARS)
            if not drafts:
                raise ValueError("The source contains no readable text.")
            await update_job(session_factory, job_id, stage="indexing", progress=20)
            chunks = await store_chunks(session, source, drafts)
            await lexical_search.index_chunks(session, chunks)
            vectors = await embedder.embed_documents([c.text for c in chunks])
            retrieval_mode = "hybrid"
            if vectors is None:
                retrieval_mode = "bm25_only"
            else:
                for chunk, vector in zip(chunks, vectors):
                    chunk.embedding_json = vector
            await session.commit()
            chunk_ids = [c.id for c in chunks]
            roles = roles_for((source.metadata_json or {}).get("participants", []), (source.metadata_json or {}).get("me"))

        stats = ExtractionStats()
        failed_batches = 0
        async with session_factory() as session:
            rows = list(
                (
                    await session.execute(
                        select(SourceChunk).where(SourceChunk.id.in_(chunk_ids)).order_by(SourceChunk.ordinal)
                    )
                ).scalars()
            )
            batches = make_batches(rows, settings.EXTRACTION_BATCH_CHARS)
            for number, batch in enumerate(batches, start=1):
                await update_job(
                    session_factory,
                    job_id,
                    stage=f"extracting {number}/{len(batches)}",
                    progress=30 + int(60 * (number - 1) / len(batches)),
                )
                try:
                    output = await extract_batch(llm, batch, roles)
                except OllamaBadResponse as exc:
                    failed_batches += 1
                    logger.warning("extraction_batch_failed", batch=number, error=str(exc))
                    continue
                stats.merge(
                    await persist_extraction(
                        session,
                        project_id=source.project_id,
                        source_id=source_id,
                        chunks=batch,
                        output=output,
                        roles=roles,
                        evidence_kind=evidence_kind_for(source_type),
                    )
                )
                await session.commit()

        if failed_batches == len(batches):
            raise OllamaBadResponse("The model could not produce valid output for any part of this source.")

        async with session_factory() as session:
            source = await session.get(Source, source_id)
            source.status = SourceStatus.PROCESSED
            source.processed_at = datetime.now(timezone.utc)
            await session.commit()
        result = {
            **stats.to_dict(),
            "chunks": len(chunk_ids),
            "failed_batches": failed_batches,
            "retrieval_mode": retrieval_mode,
        }
        await update_job(
            session_factory, job_id, status=JobStatus.COMPLETED, stage="complete", progress=100, result=result
        )
    except (OllamaError, ValueError, MediaError) as exc:
        await _fail(session_factory, source_id, job_id, str(exc))
    except Exception:
        logger.exception("ingestion_failed", source_id=source_id)
        await _fail(session_factory, source_id, job_id, "Processing failed unexpectedly. Check the server logs.")


async def _fail(
    session_factory: async_sessionmaker[AsyncSession], source_id: str, job_id: str, message: str
) -> None:
    async with session_factory() as session:
        source = await session.get(Source, source_id)
        if source is not None:
            source.status = SourceStatus.FAILED
            source.error_message = message
            await session.commit()
    await update_job(session_factory, job_id, status=JobStatus.FAILED, stage="failed", error=message)
