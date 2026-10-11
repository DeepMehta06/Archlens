"""Project CRUD."""
import shutil

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.deps import project_or_404
from app.models import Project
from app.schemas import ProjectCreate, ProjectOut, ProjectUpdate
from app.services import lexical_search

router = APIRouter(prefix="/api", tags=["projects"])


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, session: AsyncSession = Depends(get_db)) -> Project:
    project = Project(name=body.name.strip(), description=body.description, my_name=body.my_name)
    session.add(project)
    await session.flush()
    return project


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects(session: AsyncSession = Depends(get_db)) -> list[Project]:
    rows = await session.execute(select(Project).order_by(Project.created_at.desc()))
    return list(rows.scalars())


@router.get("/projects/{project_id}", response_model=ProjectOut)
async def get_project(project_id: str, session: AsyncSession = Depends(get_db)) -> Project:
    return await project_or_404(session, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: str, body: ProjectUpdate, session: AsyncSession = Depends(get_db)
) -> Project:
    project = await project_or_404(session, project_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value.strip() if isinstance(value, str) else value)
    await session.flush()
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, session: AsyncSession = Depends(get_db)) -> None:
    project = await project_or_404(session, project_id)
    await lexical_search.delete_project_index(session, project_id)
    await session.delete(project)
    shutil.rmtree(get_settings().uploads_dir / project_id, ignore_errors=True)
