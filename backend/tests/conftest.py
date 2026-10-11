import os

os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import pytest

from app.database import init_db, make_engine, make_session_factory


@pytest.fixture
async def engine():
    engine = make_engine("sqlite+aiosqlite://", in_memory=True)
    await init_db(engine)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_factory(engine):
    return make_session_factory(engine)


@pytest.fixture
async def session(session_factory):
    async with session_factory() as session:
        yield session
