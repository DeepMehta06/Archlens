"""Scope brief export: Markdown (always available) and Notion (requires configuration)."""
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_notion_client, project_or_404
from app.schemas import NotionExportOut
from app.services.export_service import build_markdown
from app.services.notion_export import NotionClient, NotionError, export_project

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


@router.post(
    "/projects/{project_id}/export/notion", response_model=NotionExportOut, status_code=201
)
async def export_notion(
    project_id: str,
    session: AsyncSession = Depends(get_db),
    notion: NotionClient = Depends(get_notion_client),
) -> NotionExportOut:
    project = await project_or_404(session, project_id)
    try:
        result = await export_project(session, project, notion)
    except NotionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return NotionExportOut(page_id=result.page_id, url=result.url)
