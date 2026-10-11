"""Ledger persistence helpers: display ids, duplicate detection and read-model summaries."""
import re
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import (
    ITEM_PREFIXES,
    ApprovalStatus,
    EvidenceStatus,
    ItemType,
    QuestionStatus,
    RiskLevel,
    StatedBy,
    VerificationStatus,
)
from app.models import LedgerItem, Question
from app.schemas import LedgerItemOut
from app.services import lexical_search

_TOKEN = re.compile(r"[\wऀ-ॿ]{2,}", re.UNICODE)
DUPLICATE_THRESHOLD = 0.75


def _stem(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def title_tokens(title: str) -> set[str]:
    return {_stem(t) for t in _TOKEN.findall(title.casefold())}


def is_similar_title(a: str, b: str) -> bool:
    ta, tb = title_tokens(a), title_tokens(b)
    if not ta or not tb:
        return a.strip().casefold() == b.strip().casefold()
    return len(ta & tb) / len(ta | tb) >= DUPLICATE_THRESHOLD


async def next_display_id(session: AsyncSession, project_id: str, item_type: ItemType) -> str:
    prefix = ITEM_PREFIXES[item_type]
    existing = (
        await session.execute(
            select(LedgerItem.display_id).where(
                LedgerItem.project_id == project_id, LedgerItem.display_id.like(f"{prefix}-%")
            )
        )
    ).scalars()
    numbers = [int(d.split("-")[1]) for d in existing if d.split("-")[1].isdigit()]
    return f"{prefix}-{(max(numbers) if numbers else 0) + 1:03d}"


async def find_duplicate(
    session: AsyncSession, project_id: str, item_type: ItemType, title: str
) -> Optional[LedgerItem]:
    candidates = (
        await session.execute(
            select(LedgerItem).where(
                LedgerItem.project_id == project_id,
                LedgerItem.item_type == item_type,
                LedgerItem.active.is_(True),
                LedgerItem.approval_status != ApprovalStatus.REJECTED,
            )
        )
    ).scalars()
    return next((c for c in candidates if is_similar_title(c.title, title)), None)


async def create_item(
    session: AsyncSession,
    project_id: str,
    *,
    item_type: ItemType,
    title: str,
    description: str,
    evidence_status: EvidenceStatus,
    risk_level: RiskLevel,
    stated_by: StatedBy,
) -> LedgerItem:
    item = LedgerItem(
        project_id=project_id,
        display_id=await next_display_id(session, project_id, item_type),
        item_type=item_type,
        title=title[:300],
        description=description,
        evidence_status=evidence_status,
        approval_status=ApprovalStatus.NEEDS_REVIEW,
        risk_level=risk_level,
        stated_by=stated_by,
        evidence_links=[],
    )
    session.add(item)
    await session.flush()
    await lexical_search.index_item(session, item)
    return item


async def open_question_counts(session: AsyncSession, project_id: str) -> dict[str, int]:
    rows = await session.execute(
        select(Question.ledger_item_id, func.count())
        .where(
            Question.project_id == project_id,
            Question.status == QuestionStatus.OPEN,
            Question.ledger_item_id.is_not(None),
        )
        .group_by(Question.ledger_item_id)
    )
    return {item_id: count for item_id, count in rows}


def to_item_out(item: LedgerItem, open_questions: int = 0) -> LedgerItemOut:
    out = LedgerItemOut.model_validate(item)
    out.evidence_total = len(item.evidence_links)
    out.evidence_verified = sum(
        1 for e in item.evidence_links if e.verification_status == VerificationStatus.VERIFIED
    )
    out.open_questions = open_questions
    return out
