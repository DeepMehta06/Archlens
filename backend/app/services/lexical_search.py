"""SQLite FTS5 lexical search (BM25) over source chunks and ledger items.

The ordinary tables stay the source of truth; the FTS tables are indexes keyed by id.
FTS5 ``bm25()`` returns lower values for better matches, so results are sorted ascending.
User text is tokenised and quoted, never interpolated into the MATCH expression.
"""
import re
from collections.abc import Iterable
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LedgerItem, SourceChunk

_TOKEN = re.compile(r"[\wऀ-ॿ]+", re.UNICODE)
MAX_QUERY_TOKENS = 24


def build_match_query(query: str) -> Optional[str]:
    tokens: list[str] = []
    for token in _TOKEN.findall(query.casefold()):
        if (len(token) >= 2 or token.isdigit()) and token not in tokens:
            tokens.append(token)
    if not tokens:
        return None
    return " OR ".join(f'"{t}"' for t in tokens[:MAX_QUERY_TOKENS])


async def index_chunks(session: AsyncSession, chunks: Iterable[SourceChunk]) -> None:
    for chunk in chunks:
        await session.execute(text("DELETE FROM chunk_fts WHERE chunk_id = :id"), {"id": chunk.id})
        await session.execute(
            text("INSERT INTO chunk_fts (chunk_id, project_id, text) VALUES (:id, :pid, :text)"),
            {"id": chunk.id, "pid": chunk.project_id, "text": chunk.text},
        )


async def delete_source_index(session: AsyncSession, source_id: str) -> None:
    await session.execute(
        text("DELETE FROM chunk_fts WHERE chunk_id IN (SELECT id FROM source_chunks WHERE source_id = :sid)"),
        {"sid": source_id},
    )


async def delete_project_index(session: AsyncSession, project_id: str) -> None:
    for table in ("chunk_fts", "item_fts"):
        await session.execute(text(f"DELETE FROM {table} WHERE project_id = :pid"), {"pid": project_id})


async def search_chunks(
    session: AsyncSession, project_id: str, query: str, limit: int = 10
) -> list[tuple[str, float]]:
    match = build_match_query(query)
    if match is None:
        return []
    result = await session.execute(
        text(
            "SELECT chunk_id, bm25(chunk_fts) AS score FROM chunk_fts "
            "WHERE chunk_fts MATCH :match AND project_id = :pid ORDER BY score ASC LIMIT :limit"
        ),
        {"match": match, "pid": project_id, "limit": limit},
    )
    return [(row[0], row[1]) for row in result]


def _item_text(item: LedgerItem) -> str:
    return f"{item.display_id} {item.title} {item.description}"


async def index_item(session: AsyncSession, item: LedgerItem) -> None:
    await session.execute(text("DELETE FROM item_fts WHERE item_id = :id"), {"id": item.id})
    await session.execute(
        text("INSERT INTO item_fts (item_id, project_id, text) VALUES (:id, :pid, :text)"),
        {"id": item.id, "pid": item.project_id, "text": _item_text(item)},
    )


async def search_items(
    session: AsyncSession, project_id: str, query: str, limit: int = 10
) -> list[tuple[str, float]]:
    match = build_match_query(query)
    if match is None:
        return []
    result = await session.execute(
        text(
            "SELECT item_id, bm25(item_fts) AS score FROM item_fts "
            "WHERE item_fts MATCH :match AND project_id = :pid ORDER BY score ASC LIMIT :limit"
        ),
        {"match": match, "pid": project_id, "limit": limit},
    )
    return [(row[0], row[1]) for row in result]
