"""Project chat: a server-sent event stream plus message history."""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.deps import get_chat_deps
from app.models import ChatMessage, ChatThread, Project
from app.rate_limit import limiter, llm_limit
from app.schemas import ChatMessageOut, ChatRequest
from app.services.chat_orchestrator import ChatDeps, get_or_create_thread, run_turn

router = APIRouter(prefix="/api", tags=["chat"])


def _sse(event: dict) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


@router.post("/projects/{project_id}/chat")
@limiter.limit(llm_limit)
async def chat(
    request: Request, project_id: str, body: ChatRequest, deps: ChatDeps = Depends(get_chat_deps)
) -> StreamingResponse:
    async with deps.session_factory() as session:
        if await session.get(Project, project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        if body.thread_id:
            thread = await session.get(ChatThread, body.thread_id)
            if thread is None or thread.project_id != project_id:
                raise HTTPException(status_code=404, detail="Chat thread not found in this project.")

    async def stream():
        async for event in run_turn(deps, project_id, body.message, body.thread_id):
            yield _sse(event)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/projects/{project_id}/chat/messages", response_model=list[ChatMessageOut])
async def chat_messages(
    project_id: str, thread_id: Optional[str] = None, deps: ChatDeps = Depends(get_chat_deps)
) -> list[ChatMessage]:
    async with deps.session_factory() as session:
        if await session.get(Project, project_id) is None:
            raise HTTPException(status_code=404, detail="Project not found")
        try:
            thread = await get_or_create_thread(session, project_id, thread_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        await session.commit()
        rows = await session.execute(
            select(ChatMessage).where(ChatMessage.thread_id == thread.id).order_by(ChatMessage.created_at)
        )
        return list(rows.scalars())
