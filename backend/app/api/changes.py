"""Approved-scope snapshots and incoming-request comparison."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_embedder, get_llm, get_retriever, project_or_404
from app.models import ChangeReport, ScopeSnapshot
from app.schemas import (
    ChangeReportOut,
    ChangeResult,
    CompareRequest,
    SnapshotCreate,
    SnapshotOut,
)
from app.services.change_detection import compare_request
from app.services.embeddings import EmbeddingService
from app.services.hybrid_retrieval import Retriever
from app.services.snapshots import NoApprovedItems, create_snapshot

router = APIRouter(prefix="/api", tags=["changes"])


def _report_out(report: ChangeReport) -> ChangeReportOut:
    return ChangeReportOut(
        id=report.id,
        project_id=report.project_id,
        source_id=report.source_id,
        snapshot_id=report.snapshot_id,
        results=[ChangeResult.model_validate(r) for r in report.results_json["results"]],
        draft_message=report.draft_message,
        created_at=report.created_at,
    )


@router.post(
    "/projects/{project_id}/snapshots", response_model=SnapshotOut, status_code=status.HTTP_201_CREATED
)
async def make_snapshot(
    project_id: str, body: SnapshotCreate, session: AsyncSession = Depends(get_db)
) -> ScopeSnapshot:
    await project_or_404(session, project_id)
    try:
        return await create_snapshot(session, project_id, body.label)
    except NoApprovedItems as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/projects/{project_id}/snapshots", response_model=list[SnapshotOut])
async def list_snapshots(project_id: str, session: AsyncSession = Depends(get_db)) -> list[ScopeSnapshot]:
    await project_or_404(session, project_id)
    rows = await session.execute(
        select(ScopeSnapshot).where(ScopeSnapshot.project_id == project_id).order_by(ScopeSnapshot.version)
    )
    return list(rows.scalars())


@router.post("/projects/{project_id}/compare", response_model=ChangeReportOut)
async def compare(
    project_id: str,
    body: CompareRequest,
    session: AsyncSession = Depends(get_db),
    llm=Depends(get_llm),
    retriever: Retriever = Depends(get_retriever),
    embedder: EmbeddingService = Depends(get_embedder),
) -> ChangeReportOut:
    project = await project_or_404(session, project_id)
    snapshot = await session.get(ScopeSnapshot, body.snapshot_id)
    if snapshot is None or snapshot.project_id != project_id:
        raise HTTPException(status_code=404, detail="Snapshot not found in this project.")
    report = await compare_request(
        session,
        llm=llm,
        retriever=retriever,
        embedder=embedder,
        project=project,
        snapshot=snapshot,
        incoming_text=body.incoming_text,
    )
    return _report_out(report)


@router.get("/change-reports/{report_id}", response_model=ChangeReportOut)
async def get_report(report_id: str, session: AsyncSession = Depends(get_db)) -> ChangeReportOut:
    report = await session.get(ChangeReport, report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Change report not found")
    return _report_out(report)
