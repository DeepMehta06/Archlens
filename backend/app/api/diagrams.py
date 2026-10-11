"""Diagram generation from the scope ledger."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_llm, project_or_404
from app.models import Diagram
from app.rate_limit import limiter, llm_limit
from app.schemas import DiagramCreate, DiagramOut
from app.services.diagrams import NothingToDraw, generate_diagram

router = APIRouter(prefix="/api", tags=["diagrams"])


@router.post(
    "/projects/{project_id}/diagrams", response_model=DiagramOut, status_code=status.HTTP_201_CREATED
)
@limiter.limit(llm_limit)
async def create_diagram(
    request: Request,
    project_id: str,
    body: DiagramCreate,
    session: AsyncSession = Depends(get_db),
    llm=Depends(get_llm),
) -> Diagram:
    await project_or_404(session, project_id)
    try:
        return await generate_diagram(session, llm, project_id, body.diagram_type, body.focus)
    except NothingToDraw as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/projects/{project_id}/diagrams", response_model=list[DiagramOut])
async def list_diagrams(project_id: str, session: AsyncSession = Depends(get_db)) -> list[Diagram]:
    await project_or_404(session, project_id)
    rows = await session.execute(
        select(Diagram).where(Diagram.project_id == project_id).order_by(Diagram.created_at.desc())
    )
    return list(rows.scalars())
