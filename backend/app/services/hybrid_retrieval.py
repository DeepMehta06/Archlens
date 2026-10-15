"""Hybrid retrieval: FTS5 BM25 plus dense embeddings fused with Reciprocal Rank Fusion.

Every query is filtered by project. RRF combines ranks only. If the embedding model is
unavailable the result is explicitly reported as ``bm25_only``. The dense channel itself
uses an ANN index above ``ANN_MIN_VECTORS`` per project (see ``ann_index.py``) and exact
brute-force cosine below it; either way the result shape is the same.
"""
from typing import Any, Literal, Optional

import numpy as np
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import LedgerItem, Source, SourceChunk
from app.services import lexical_search
from app.services.ann_index import AnnIndexService
from app.services.embeddings import EmbeddingService
from app.services.rrf import reciprocal_rank_fusion


class RetrievalHit(BaseModel):
    candidate_id: str
    candidate_type: Literal["chunk", "ledger_item"]
    source_id: Optional[str] = None
    chunk_id: Optional[str] = None
    ledger_item_id: Optional[str] = None
    text: str
    bm25_rank: Optional[int] = None
    dense_rank: Optional[int] = None
    rrf_score: float
    location: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    hits: list[RetrievalHit]
    mode: Literal["hybrid", "bm25_only"]


class Retriever:
    def __init__(
        self,
        embedder: EmbeddingService,
        settings: Optional[Settings] = None,
        ann: Optional[AnnIndexService] = None,
    ):
        self._embedder = embedder
        self._settings = settings or get_settings()
        self._ann = ann or AnnIndexService(self._settings)

    async def mode(self) -> Literal["hybrid", "bm25_only"]:
        return "hybrid" if await self._embedder.available() else "bm25_only"

    async def _dense_ranking(
        self, session: AsyncSession, project_id: str, query: str, limit: int, include_code: bool
    ) -> Optional[list[str]]:
        query_vector = await self._embedder.embed_query(query)
        if query_vector is None:
            return None
        rows = (
            await session.execute(
                select(SourceChunk.id, SourceChunk.embedding_json)
                .join(Source, Source.id == SourceChunk.source_id)
                .where(
                    SourceChunk.project_id == project_id,
                    SourceChunk.embedding_json.is_not(None),
                    (Source.source_type == "github_repo") if include_code else (Source.source_type != "github_repo"),
                )
            )
        ).all()
        if not rows:
            return []
        ids = [r[0] for r in rows]
        matrix = np.asarray([r[1] for r in rows], dtype=np.float32)
        cache_key = f"{project_id}:{'code' if include_code else 'conversation'}"
        hits = await self._ann.search(cache_key, ids, matrix, query_vector, limit)
        return [chunk_id for chunk_id, _ in hits]

    async def search_chunks(
        self,
        session: AsyncSession,
        project_id: str,
        query: str,
        top_k: Optional[int] = None,
        include_code: bool = False,
    ) -> RetrievalResult:
        """Searches conversation/document chunks by default; ``include_code=True`` searches a
        connected github_repo source's chunks instead. The two domains are never mixed in one
        call -- see lexical_search.search_chunks and _dense_ranking."""
        top_k = top_k or self._settings.RETRIEVAL_TOP_K
        bm25 = [
            cid for cid, _ in await lexical_search.search_chunks(session, project_id, query, 10, include_code)
        ]
        dense = await self._dense_ranking(session, project_id, query, 10, include_code)
        mode: Literal["hybrid", "bm25_only"] = "bm25_only" if dense is None else "hybrid"
        rankings = {"bm25": bm25}
        if dense is not None:
            rankings["dense"] = dense
        fused = reciprocal_rank_fusion(
            rankings, k=self._settings.RRF_K, weights={"dense": self._settings.RRF_DENSE_WEIGHT}
        )[:top_k]
        if not fused:
            return RetrievalResult(hits=[], mode=mode)

        chunks = {
            c.id: c
            for c in (
                await session.execute(
                    select(SourceChunk).where(
                        SourceChunk.project_id == project_id, SourceChunk.id.in_([f.id for f in fused])
                    )
                )
            ).scalars()
        }
        labels = {
            s.id: s.label
            for s in (
                await session.execute(
                    select(Source).where(Source.id.in_({c.source_id for c in chunks.values()}))
                )
            ).scalars()
        }
        hits = [
            RetrievalHit(
                candidate_id=f"chunk:{f.id}",
                candidate_type="chunk",
                source_id=chunks[f.id].source_id,
                chunk_id=f.id,
                text=chunks[f.id].text,
                bm25_rank=f.ranks.get("bm25"),
                dense_rank=f.ranks.get("dense"),
                rrf_score=f.score,
                location={
                    "source_label": labels.get(chunks[f.id].source_id),
                    "ordinal": chunks[f.id].ordinal,
                    "message_index": chunks[f.id].message_index,
                    "sender": chunks[f.id].sender,
                    "timestamp_text": chunks[f.id].timestamp_text,
                },
            )
            for f in fused
            if f.id in chunks
        ]
        return RetrievalResult(hits=hits, mode=mode)

    async def search_items(
        self, session: AsyncSession, project_id: str, query: str, top_k: Optional[int] = None
    ) -> list[RetrievalHit]:
        top_k = top_k or self._settings.RETRIEVAL_TOP_K
        ranked = [iid for iid, _ in await lexical_search.search_items(session, project_id, query, top_k)]
        if not ranked:
            return []
        items = {
            i.id: i
            for i in (
                await session.execute(
                    select(LedgerItem).where(LedgerItem.project_id == project_id, LedgerItem.id.in_(ranked))
                )
            ).scalars()
        }
        return [
            RetrievalHit(
                candidate_id=f"item:{iid}",
                candidate_type="ledger_item",
                ledger_item_id=iid,
                text=f"{items[iid].title}: {items[iid].description}",
                bm25_rank=rank,
                rrf_score=1.0 / (self._settings.RRF_K + rank),
                location={"display_id": items[iid].display_id, "approval_status": items[iid].approval_status.value},
            )
            for rank, iid in enumerate(ranked, start=1)
            if iid in items
        ]
