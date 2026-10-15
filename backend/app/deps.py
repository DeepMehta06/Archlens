"""FastAPI dependency providers. Tests override these to inject fakes and an in-memory database."""
from functools import lru_cache

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import get_db, get_session_factory
from app.models import Project
from app.services.chat_orchestrator import ChatDeps
from app.services.embeddings import EmbeddingService
from app.services.github_client import GitHubClient
from app.services.hybrid_retrieval import Retriever
from app.services.notion_export import NotionClient
from app.services.ollama_client import OllamaClient


@lru_cache
def _llm() -> OllamaClient:
    return OllamaClient()


@lru_cache
def _embedder() -> EmbeddingService:
    return EmbeddingService(_llm())


@lru_cache
def _notion_client() -> NotionClient:
    return NotionClient()


@lru_cache
def _github_client() -> GitHubClient:
    return GitHubClient()


def get_llm() -> OllamaClient:
    return _llm()


def get_embedder() -> EmbeddingService:
    return _embedder()


def get_notion_client() -> NotionClient:
    return _notion_client()


def get_github_client() -> GitHubClient:
    return _github_client()


def get_retriever(embedder: EmbeddingService = Depends(get_embedder)) -> Retriever:
    return Retriever(embedder)


def get_session_factory_dep() -> async_sessionmaker[AsyncSession]:
    return get_session_factory()


def get_chat_deps(
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory_dep),
    llm=Depends(get_llm),
    retriever: Retriever = Depends(get_retriever),
    embedder: EmbeddingService = Depends(get_embedder),
) -> ChatDeps:
    return ChatDeps(session_factory=factory, llm=llm, retriever=retriever, embedder=embedder)


async def project_or_404(session: AsyncSession, project_id: str) -> Project:
    from fastapi import HTTPException

    project = (await session.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


__all__ = [
    "get_db",
    "get_llm",
    "get_embedder",
    "get_notion_client",
    "get_github_client",
    "get_retriever",
    "get_session_factory_dep",
    "get_chat_deps",
    "project_or_404",
]
