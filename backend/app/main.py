"""ArchLens FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api import changes, chat, demo, diagrams, exports, health, ledger, projects, questions, sources
from app.config import get_settings
from app.database import get_engine, init_db
from app.deps import get_github_client, get_llm, get_notion_client
from app.logging_config import configure_logging, get_logger
from app.rate_limit import limiter
from app.services.ollama_client import OllamaError

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(get_engine())
    status = await get_llm().health()
    logger.info(
        "archlens_startup",
        version=settings.APP_VERSION,
        data_dir=str(settings.data_dir),
        ollama_reachable=status["reachable"],
        model=status["model"],
        model_installed=status["model_installed"],
        embed_model_installed=status["embed_model_installed"],
    )
    yield
    await get_llm().aclose()
    await get_notion_client().aclose()
    await get_github_client().aclose()
    await get_engine().dispose()


app = FastAPI(
    title="ArchLens",
    description="Evidence-backed scope ledger for client conversations, powered by local Gemma.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(OllamaError)
async def ollama_error_handler(request: Request, exc: OllamaError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": {"error_code": type(exc).__name__, "message": str(exc)}},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", path=request.url.path, error=type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"detail": {"error_code": "InternalError", "message": "An unexpected error occurred."}},
    )


for module in (health, projects, sources, ledger, questions, changes, diagrams, exports, chat, demo):
    app.include_router(module.router)


@app.get("/")
async def root() -> dict:
    return {"name": "ArchLens", "version": settings.APP_VERSION, "docs": "/docs"}
