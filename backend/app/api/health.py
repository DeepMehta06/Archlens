"""Health endpoint: Ollama reachability, installed models and retrieval mode."""
from fastapi import APIRouter, Depends

from app.config import get_settings
from app.deps import get_llm, get_retriever
from app.schemas import HealthOut
from app.services.hybrid_retrieval import Retriever

router = APIRouter(prefix="/api", tags=["health"])

PRIVACY = (
    "Model inference runs locally through Ollama on this machine and no cloud AI provider is used. "
    "Model downloads and development tooling can still use the network."
)


@router.get("/health", response_model=HealthOut)
async def health(llm=Depends(get_llm), retriever: Retriever = Depends(get_retriever)) -> HealthOut:
    settings = get_settings()
    status = await llm.health()
    ready = status["reachable"] and status["model_installed"]
    return HealthOut(
        status="ok" if ready else "degraded",
        version=settings.APP_VERSION,
        ollama_reachable=status["reachable"],
        model=status["model"],
        model_installed=status["model_installed"],
        embed_model=status["embed_model"],
        embed_model_installed=status["embed_model_installed"],
        retrieval_mode=await retriever.mode(),
        fts5=True,
        privacy=PRIVACY,
        error=status["error"] or (None if status["model_installed"] else f"Model not installed. Run: ollama pull {status['model']}"),
    )
