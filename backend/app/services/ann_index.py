"""Approximate nearest-neighbour search over per-project chunk embeddings.

One HNSW graph is kept in process memory per project and rebuilt whenever the
set of embedded chunk ids for that project changes. Below ``ANN_MIN_VECTORS``,
or if hnswlib is not installed, or if a build/query fails, callers fall back to
exact brute-force cosine (``embeddings.cosine_top_k``) -- the index is a speed
optimisation only, never a different source of truth from the exact channel.
"""
from __future__ import annotations

import asyncio
from typing import Optional

import numpy as np

from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.services.embeddings import cosine_top_k

logger = get_logger(__name__)

try:
    import hnswlib

    HNSWLIB_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only when the dependency is absent
    HNSWLIB_AVAILABLE = False


class _ProjectIndex:
    __slots__ = ("index", "ids", "id_set")

    def __init__(self, index: "hnswlib.Index", ids: list[str]):
        self.index = index
        self.ids = ids
        self.id_set = frozenset(ids)


def _build(ids: list[str], matrix: np.ndarray, settings: Settings) -> _ProjectIndex:
    index = hnswlib.Index(space="cosine", dim=matrix.shape[1])
    index.init_index(
        max_elements=len(ids),
        ef_construction=settings.ANN_EF_CONSTRUCTION,
        M=settings.ANN_M,
    )
    index.add_items(matrix, np.arange(len(ids)))
    index.set_ef(settings.ANN_EF_SEARCH)
    return _ProjectIndex(index=index, ids=ids)


class AnnIndexService:
    """Per-project HNSW cache with an exact brute-force fallback."""

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._cache: dict[str, _ProjectIndex] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, project_id: str) -> asyncio.Lock:
        lock = self._locks.get(project_id)
        if lock is None:
            lock = self._locks[project_id] = asyncio.Lock()
        return lock

    def invalidate(self, project_id: str) -> None:
        self._cache.pop(project_id, None)

    async def search(
        self,
        project_id: str,
        ids: list[str],
        matrix: np.ndarray,
        query_vector: list[float],
        k: int,
    ) -> list[tuple[str, float]]:
        if not ids:
            return []
        if not HNSWLIB_AVAILABLE or not self._settings.ANN_ENABLED or len(ids) < self._settings.ANN_MIN_VECTORS:
            return cosine_top_k(query_vector, ids, matrix, k)

        id_set = frozenset(ids)
        cached = self._cache.get(project_id)
        if cached is None or cached.id_set != id_set:
            async with self._lock_for(project_id):
                cached = self._cache.get(project_id)
                if cached is None or cached.id_set != id_set:
                    try:
                        cached = await asyncio.to_thread(self._build_safe, ids, matrix)
                    except Exception as exc:  # noqa: BLE001 - any build failure degrades to exact search
                        logger.warning("ann_build_failed", project_id=project_id, error=str(exc))
                        return cosine_top_k(query_vector, ids, matrix, k)
                    self._cache[project_id] = cached
                    logger.info("ann_index_built", project_id=project_id, vectors=len(ids))

        try:
            query = np.asarray([query_vector], dtype=np.float32)
            labels, distances = await asyncio.to_thread(cached.index.knn_query, query, k=min(k, len(cached.ids)))
        except Exception as exc:  # noqa: BLE001 - query failure degrades to exact search, never an error
            logger.warning("ann_query_failed", project_id=project_id, error=str(exc))
            return cosine_top_k(query_vector, ids, matrix, k)

        return [(cached.ids[i], 1.0 - float(d)) for i, d in zip(labels[0], distances[0])]

    def _build_safe(self, ids: list[str], matrix: np.ndarray) -> _ProjectIndex:
        return _build(ids, matrix, self._settings)
