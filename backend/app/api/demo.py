"""Demo project seeding. Seeded content is clearly labelled and runs through the real pipeline."""
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import get_db
from app.deps import get_embedder, get_llm, get_session_factory_dep
from app.models import Project, Source
from app.schemas import JobOut, ProjectOut, SourceOut
from app.services.embeddings import EmbeddingService
from app.services.jobs import create_job
from app.services.source_ingestion import create_text_source, process_source

router = APIRouter(prefix="/api", tags=["demo"])

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"
DEMO_NAME = "Pune Clinic App (demo data)"


@router.post("/demo/seed", status_code=status.HTTP_201_CREATED)
async def seed_demo(
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory_dep),
    llm=Depends(get_llm),
    embedder: EmbeddingService = Depends(get_embedder),
) -> dict:
    compare_example = (DEMO_DIR / "incoming_request.txt").read_text(encoding="utf-8").strip()
    existing = (
        await session.execute(select(Project).where(Project.is_demo.is_(True), Project.name == DEMO_NAME))
    ).scalar_one_or_none()
    if existing is not None:
        sources = (await session.execute(select(Source).where(Source.project_id == existing.id))).scalars().all()
        return {
            "project": ProjectOut.model_validate(existing),
            "sources": [SourceOut.model_validate(s) for s in sources],
            "job": None,
            "compare_example": compare_example,
            "created": False,
        }

    project = Project(
        name=DEMO_NAME,
        description="Demo data: a short Hinglish WhatsApp conversation about a clinic booking app.",
        my_name="Riya",
        is_demo=True,
    )
    session.add(project)
    await session.flush()
    chat_text = (DEMO_DIR / "pune_clinic_chat.txt").read_text(encoding="utf-8")
    source = await create_text_source(
        session, project, chat_text, label="DEMO DATA: clinic WhatsApp chat", filename="pune_clinic_chat.txt"
    )
    job = await create_job(session, project.id, source.id, "ingest")
    await session.commit()
    background.add_task(process_source, factory, llm, embedder, source.id, job.id)
    return {
        "project": ProjectOut.model_validate(project),
        "sources": [SourceOut.model_validate(source)],
        "job": JobOut.model_validate(job),
        "compare_example": compare_example,
        "created": True,
    }
