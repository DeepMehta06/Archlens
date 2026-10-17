"""Job bookkeeping. Updates use their own short transactions so polling sees live progress."""
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import retry_on_locked
from app.enums import JobStatus, SourceStatus
from app.models import Job, Source


async def create_job(
    session: AsyncSession, project_id: str, source_id: Optional[str], job_type: str
) -> Job:
    job = Job(project_id=project_id, source_id=source_id, job_type=job_type)
    session.add(job)
    await session.flush()
    return job


async def update_job(
    session_factory: async_sessionmaker[AsyncSession],
    job_id: str,
    *,
    status: Optional[JobStatus] = None,
    stage: Optional[str] = None,
    progress: Optional[int] = None,
    error: Optional[str] = None,
    result: Optional[dict[str, Any]] = None,
) -> None:
    async def _apply(session: AsyncSession) -> None:
        job = await session.get(Job, job_id)
        if job is None:
            return
        if status is not None:
            job.status = status
        if stage is not None:
            job.stage = stage
        if progress is not None:
            job.progress = progress
        if error is not None:
            job.error_message = error
        if result is not None:
            job.result_json = result

    await retry_on_locked(session_factory, _apply)


async def fail_source_and_job(
    session_factory: async_sessionmaker[AsyncSession], source_id: str, job_id: str, message: str
) -> None:
    async def _apply(session: AsyncSession) -> None:
        source = await session.get(Source, source_id)
        if source is not None:
            source.status = SourceStatus.FAILED
            source.error_message = message

    await retry_on_locked(session_factory, _apply)
    await update_job(session_factory, job_id, status=JobStatus.FAILED, stage="failed", error=message)
