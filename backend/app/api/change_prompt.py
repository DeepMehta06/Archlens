"""Implementation-brief generation: a ledger item plus a connected repo becomes a prompt the
user hands to their own coding agent. ArchLens never writes code or touches the repo itself."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_llm, get_retriever
from app.rate_limit import limiter, llm_limit
from app.schemas import ChangePromptOut, ChangePromptRequest
from app.services.change_prompt import NoLedgerItem, NoRepositoryConnected, build_change_prompt
from app.services.hybrid_retrieval import Retriever

router = APIRouter(prefix="/api", tags=["change-prompt"])


@router.post("/ledger-items/{item_id}/prompt", response_model=ChangePromptOut)
@limiter.limit(llm_limit)
async def create_change_prompt(
    request: Request,
    item_id: str,
    body: ChangePromptRequest,
    session: AsyncSession = Depends(get_db),
    llm=Depends(get_llm),
    retriever: Retriever = Depends(get_retriever),
) -> ChangePromptOut:
    try:
        result = await build_change_prompt(session, llm, retriever, item_id, body.target)
    except NoLedgerItem as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoRepositoryConnected as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ChangePromptOut(prompt=result.prompt, target=result.target, affected_files=result.affected_files)
