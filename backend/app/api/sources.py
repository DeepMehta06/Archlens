"""Source import (pasted text, WhatsApp exports) and job status."""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.database import get_db
from app.deps import get_embedder, get_llm, get_session_factory_dep, project_or_404
from app.models import Job, Source, SourceChunk
from app.schemas import ChunkOut, JobOut, SourceCreated, SourceOut, SourceTextCreate, SourceUpdate
from app.services.embeddings import EmbeddingService
from app.services.jobs import create_job
from app.services.media_ingestion import source_type_for
from app.services.source_ingestion import (
    apply_me,
    create_media_source,
    create_text_source,
    decode_upload,
    process_source,
)

router = APIRouter(prefix="/api", tags=["sources"])

TEXT_EXTENSIONS = {".txt", ".md"}


async def _start(
    background: BackgroundTasks,
    session: AsyncSession,
    factory: async_sessionmaker[AsyncSession],
    llm,
    embedder: EmbeddingService,
    source: Source,
    analyze: bool,
) -> SourceCreated:
    job = None
    if analyze:
        job = await create_job(session, source.project_id, source.id, "ingest")
    await session.commit()
    if job is not None:
        background.add_task(process_source, factory, llm, embedder, source.id, job.id)
    return SourceCreated(
        source=SourceOut.model_validate(source), job=JobOut.model_validate(job) if job else None
    )


@router.get("/projects/{project_id}/sources", response_model=list[SourceOut])
async def list_sources(project_id: str, session: AsyncSession = Depends(get_db)) -> list[Source]:
    await project_or_404(session, project_id)
    rows = await session.execute(
        select(Source).where(Source.project_id == project_id).order_by(Source.created_at)
    )
    return list(rows.scalars())


@router.post(
    "/projects/{project_id}/sources", response_model=SourceCreated, status_code=status.HTTP_201_CREATED
)
async def add_text_source(
    project_id: str,
    body: SourceTextCreate,
    background: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory_dep),
    llm=Depends(get_llm),
    embedder: EmbeddingService = Depends(get_embedder),
) -> SourceCreated:
    project = await project_or_404(session, project_id)
    source = await create_text_source(session, project, body.text, label=body.label, me=body.me)
    return await _start(background, session, factory, llm, embedder, source, body.analyze)


@router.post(
    "/projects/{project_id}/sources/upload", response_model=SourceCreated, status_code=status.HTTP_201_CREATED
)
async def upload_source(
    project_id: str,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    me: Optional[str] = Form(default=None),
    analyze: bool = Form(default=True),
    session: AsyncSession = Depends(get_db),
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory_dep),
    llm=Depends(get_llm),
    embedder: EmbeddingService = Depends(get_embedder),
) -> SourceCreated:
    project = await project_or_404(session, project_id)
    settings = get_settings()
    name = file.filename or "upload"
    extension = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    media_type = source_type_for(extension)
    if extension not in TEXT_EXTENSIONS and media_type is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Supported files: .txt, .md, .pdf, .png, .jpg, .jpeg, .webp and .wav.",
        )
    data = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
        )
    if media_type is not None:
        source = await create_media_source(
            session, project, data, source_type=media_type, filename=name[:255], mime_type=file.content_type
        )
        return await _start(background, session, factory, llm, embedder, source, analyze)
    text = decode_upload(data)
    if not text.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The file is empty.")
    source = await create_text_source(
        session, project, text, me=me, filename=name[:255], mime_type=file.content_type
    )
    return await _start(background, session, factory, llm, embedder, source, analyze)


@router.get("/projects/{project_id}/sources/{source_id}")
async def get_source(
    project_id: str, source_id: str, session: AsyncSession = Depends(get_db)
) -> dict:
    await project_or_404(session, project_id)
    source = await session.get(Source, source_id)
    if source is None or source.project_id != project_id:
        raise HTTPException(status_code=404, detail="Source not found")
    chunks = (
        await session.execute(
            select(SourceChunk).where(SourceChunk.source_id == source_id).order_by(SourceChunk.ordinal)
        )
    ).scalars()
    return {
        "source": SourceOut.model_validate(source),
        "chunks": [ChunkOut.model_validate(c) for c in chunks],
    }


@router.patch("/projects/{project_id}/sources/{source_id}", response_model=SourceOut)
async def set_me(
    project_id: str, source_id: str, body: SourceUpdate, session: AsyncSession = Depends(get_db)
) -> Source:
    await project_or_404(session, project_id)
    source = await session.get(Source, source_id)
    if source is None or source.project_id != project_id:
        raise HTTPException(status_code=404, detail="Source not found")
    await apply_me(session, source, body.me)
    return source


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: str, session: AsyncSession = Depends(get_db)) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
