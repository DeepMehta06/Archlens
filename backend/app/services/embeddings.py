"""Dense embeddings through the local Ollama embedding model, with brute-force cosine search.

If the embedding model is missing or fails, callers get ``None`` and retrieval runs in an
explicitly degraded BM25-only mode instead of failing.
"""
import time
from typing import Optional

import numpy as np

from app.config import Settings, get_settings
from app.logging_config import get_logger
from app.services.ollama_client import OllamaClient, OllamaError

logger = get_logger(__name__)
AVAILABILITY_TTL_SECONDS = 30.0


def normalize_vectors(vectors: list[list[float]]) -> np.ndarray:
    matrix = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1.0, norms)


def cosine_top_k(query: list[float], ids: list[str], matrix: np.ndarray, k: int) -> list[tuple[str, float]]:
    if not ids or matrix.size == 0:
        return []
    q = normalize_vectors([query])[0]
    scores = matrix @ q
    order = np.argsort(-scores)[:k]
    return [(ids[i], float(scores[i])) for i in order]


class EmbeddingService:
    def __init__(self, client: OllamaClient, settings: Optional[Settings] = None):
        self._client = client
        self._settings = settings or get_settings()
        self._checked_at = 0.0
        self._available = False

    async def available(self) -> bool:
        if time.monotonic() - self._checked_at > AVAILABILITY_TTL_SECONDS:
            health = await self._client.health()
            self._available = bool(health["reachable"] and health["embed_model_installed"])
            self._checked_at = time.monotonic()
        return self._available

    def _mark_unavailable(self) -> None:
        self._available = False
        self._checked_at = time.monotonic()

    async def embed_documents(self, texts: list[str]) -> Optional[list[list[float]]]:
        if not texts or not await self.available():
            return None
        prefixed = [self._settings.EMBED_DOCUMENT_PREFIX + t for t in texts]
        try:
            vectors = await self._client.embed(prefixed)
        except OllamaError as exc:
            logger.warning("embedding_failed", error=str(exc))
            self._mark_unavailable()
            return None
        return normalize_vectors(vectors).tolist()

    async def embed_query(self, query: str) -> Optional[list[float]]:
        if not await self.available():
            return None
        try:
            vectors = await self._client.embed([self._settings.EMBED_QUERY_PREFIX + query])
        except OllamaError as exc:
            logger.warning("embedding_failed", error=str(exc))
            self._mark_unavailable()
            return None
        return normalize_vectors(vectors)[0].tolist()
