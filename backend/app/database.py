"""Database engine, session handling and FTS5 index setup.

The FTS5 tables are plain search indexes keyed by an unindexed id column; the ordinary
tables stay the source of truth. Devanagari combining marks are declared as token
characters because the default unicode61 tokenizer would otherwise split Hindi words.
"""
from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.models import Base

_DEVANAGARI_MARKS = "".join(
    chr(c)
    for r in ((0x0900, 0x0903), (0x093A, 0x094F), (0x0951, 0x0957), (0x0962, 0x0963))
    for c in range(r[0], r[1] + 1)
)
_TOKENIZER = f"unicode61 remove_diacritics 2 tokenchars '{_DEVANAGARI_MARKS}'"

FTS_TABLES = {
    "chunk_fts": "chunk_id",
    "item_fts": "item_id",
}


def _configure_connection(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def make_engine(url: str, in_memory: bool = False) -> AsyncEngine:
    kwargs: dict = {}
    if in_memory:
        kwargs = {"poolclass": StaticPool, "connect_args": {"check_same_thread": False}}
    engine = create_async_engine(url, **kwargs)
    event.listen(engine.sync_engine, "connect", _configure_connection)
    return engine


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    return make_engine(settings.database_url)


def make_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return make_session_factory(get_engine())


async def init_db(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for table, key in FTS_TABLES.items():
            try:
                await conn.execute(
                    text(
                        f"CREATE VIRTUAL TABLE IF NOT EXISTS {table} USING fts5("
                        f"{key} UNINDEXED, project_id UNINDEXED, text, tokenize = \"{_TOKENIZER}\")"
                    )
                )
            except Exception as exc:
                raise RuntimeError(
                    "SQLite FTS5 is unavailable in this Python build; lexical search cannot run."
                ) from exc


async def get_db() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
