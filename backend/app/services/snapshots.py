"""Immutable approved-scope snapshots. A snapshot captures only explicitly approved items."""
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ApprovalStatus
from app.models import LedgerItem, ScopeSnapshot, utcnow


class NoApprovedItems(ValueError):
    pass


def serialize_item(item: LedgerItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "display_id": item.display_id,
        "item_type": item.item_type.value,
        "title": item.title,
        "description": item.description,
        "evidence_status": item.evidence_status.value,
        "risk_level": item.risk_level.value,
        "stated_by": item.stated_by.value,
        "evidence": [
            {
                "source_id": e.source_id,
                "chunk_id": e.chunk_id,
                "quote": e.quote,
                "speaker": e.speaker,
                "speaker_role": e.speaker_role.value,
                "verification_status": e.verification_status.value,
            }
            for e in item.evidence_links
        ],
    }


async def approved_items(session: AsyncSession, project_id: str) -> list[LedgerItem]:
    rows = await session.execute(
        select(LedgerItem)
        .where(
            LedgerItem.project_id == project_id,
            LedgerItem.approval_status == ApprovalStatus.APPROVED,
            LedgerItem.active.is_(True),
        )
        .order_by(LedgerItem.display_id)
    )
    return list(rows.scalars())


async def create_snapshot(
    session: AsyncSession, project_id: str, label: Optional[str] = None
) -> ScopeSnapshot:
    items = await approved_items(session, project_id)
    if not items:
        raise NoApprovedItems("Approve at least one ledger item before creating a snapshot.")
    version = (
        await session.execute(
            select(func.coalesce(func.max(ScopeSnapshot.version), 0)).where(
                ScopeSnapshot.project_id == project_id
            )
        )
    ).scalar_one() + 1
    snapshot = ScopeSnapshot(
        project_id=project_id,
        version=version,
        label=label or f"Scope v{version}",
        snapshot_json={
            "version": version,
            "created_at": utcnow().isoformat(),
            "items": [serialize_item(i) for i in items],
        },
    )
    session.add(snapshot)
    await session.flush()
    return snapshot
