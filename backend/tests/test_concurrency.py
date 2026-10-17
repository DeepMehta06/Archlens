"""Regression test for the 'database is locked' race between a background job
writer and a concurrent foreground request, reproduced only with a real
file-backed SQLite engine (the in-memory StaticPool fixture in conftest.py
serializes all access through one connection and can't see this race)."""
import asyncio
import tempfile
from pathlib import Path

import pytest

from app.database import init_db, make_engine, make_session_factory
from app.enums import JobStatus
from app.models import Project
from app.services.jobs import create_job, update_job


@pytest.fixture
async def file_engine():
    with tempfile.TemporaryDirectory() as tmp:
        url = f"sqlite+aiosqlite:///{(Path(tmp) / 'test.db').as_posix()}"
        engine = make_engine(url)
        await init_db(engine)
        yield engine
        await engine.dispose()


@pytest.fixture
def file_session_factory(file_engine):
    return make_session_factory(file_engine)


async def test_concurrent_job_updates_do_not_raise_operational_error(file_session_factory):
    async with file_session_factory() as session:
        project = Project(name="concurrency-test")
        session.add(project)
        await session.flush()
        job = await create_job(session, project.id, None, "github_ingest")
        await session.commit()
        job_id = job.id

    async def hammer(n: int) -> None:
        for i in range(n):
            await update_job(file_session_factory, job_id, stage=f"stage-{i}", progress=i)

    # Many concurrent writers against the same row on the same file-backed
    # engine: before the fix this reliably raised
    # sqlalchemy.exc.OperationalError: database is locked.
    await asyncio.gather(*(hammer(10) for _ in range(8)))

    async with file_session_factory() as session:
        refreshed = await session.get(type(job), job_id)
        assert refreshed is not None
        assert 0 <= refreshed.progress <= 9
