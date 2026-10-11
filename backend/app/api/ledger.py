"""Scope ledger: list, inspect (with evidence and source context) and edit items."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import project_or_404
from app.enums import ApprovalStatus, EvidenceStatus, ItemType
from app.models import LedgerItem, Question, Source, SourceChunk
from app.schemas import (
    ChunkOut,
    EvidenceDetail,
    LedgerItemDetail,
    LedgerItemOut,
    LedgerItemPatch,
    QuestionOut,
)
from app.services import ledger, lexical_search

router = APIRouter(prefix="/api", tags=["ledger"])


@router.get("/projects/{project_id}/ledger", response_model=list[LedgerItemOut])
async def list_ledger(
    project_id: str,
    evidence_status: Optional[EvidenceStatus] = None,
    approval_status: Optional[ApprovalStatus] = None,
    item_type: Optional[ItemType] = None,
    session: AsyncSession = Depends(get_db),
) -> list[LedgerItemOut]:
    await project_or_404(session, project_id)
    stmt = select(LedgerItem).where(LedgerItem.project_id == project_id, LedgerItem.active.is_(True))
    if evidence_status:
        stmt = stmt.where(LedgerItem.evidence_status == evidence_status)
    if approval_status:
        stmt = stmt.where(LedgerItem.approval_status == approval_status)
    if item_type:
        stmt = stmt.where(LedgerItem.item_type == item_type)
    items = (await session.execute(stmt.order_by(LedgerItem.display_id))).scalars().all()
    counts = await ledger.open_question_counts(session, project_id)
    return [ledger.to_item_out(i, counts.get(i.id, 0)) for i in items]


async def _item_or_404(session: AsyncSession, item_id: str) -> LedgerItem:
    item = await session.get(LedgerItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Ledger item not found")
    return item


@router.get("/ledger-items/{item_id}", response_model=LedgerItemDetail)
async def get_item(item_id: str, session: AsyncSession = Depends(get_db)) -> LedgerItemDetail:
    item = await _item_or_404(session, item_id)
    questions = (
        await session.execute(select(Question).where(Question.ledger_item_id == item.id).order_by(Question.created_at))
    ).scalars().all()
    chunk_ids = {e.chunk_id for e in item.evidence_links if e.chunk_id}
    chunks = {
        c.id: c
        for c in (await session.execute(select(SourceChunk).where(SourceChunk.id.in_(chunk_ids)))).scalars()
    }
    labels = {
        s.id: s.label
        for s in (
            await session.execute(select(Source).where(Source.id.in_({e.source_id for e in item.evidence_links})))
        ).scalars()
    }
    detail = LedgerItemDetail.model_validate(ledger.to_item_out(item, sum(q.status.value == "open" for q in questions)))
    detail.evidence = [
        EvidenceDetail.model_validate(e).model_copy(
            update={
                "source_label": labels.get(e.source_id),
                "chunk": ChunkOut.model_validate(chunks[e.chunk_id]) if e.chunk_id in chunks else None,
            }
        )
        for e in item.evidence_links
    ]
    detail.questions = [QuestionOut.model_validate(q) for q in questions]
    return detail


@router.patch("/ledger-items/{item_id}", response_model=LedgerItemOut)
async def patch_item(
    item_id: str, body: LedgerItemPatch, session: AsyncSession = Depends(get_db)
) -> LedgerItemOut:
    item = await _item_or_404(session, item_id)
    changes = body.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(item, field, value.strip() if isinstance(value, str) else value)
    await session.flush()
    if {"title", "description"} & changes.keys():
        await lexical_search.index_item(session, item)
    counts = await ledger.open_question_counts(session, item.project_id)
    return ledger.to_item_out(item, counts.get(item.id, 0))
