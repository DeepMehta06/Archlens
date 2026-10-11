"""Markdown scope brief export."""
import re

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import project_or_404
from app.services.export_service import build_markdown

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/projects/{project_id}/export.md", response_class=PlainTextResponse)
async def export_markdown(project_id: str, session: AsyncSession = Depends(get_db)) -> PlainTextResponse:
    project = await project_or_404(session, project_id)
    filename = re.sub(r"[^A-Za-z0-9._-]+", "-", project.name).strip("-") or "scope-brief"
    return PlainTextResponse(
        await build_markdown(session, project),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}-scope-brief.md"'},
    )
