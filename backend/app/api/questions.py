"""Clarification questions and the client message draft."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_llm, project_or_404
from app.enums import QuestionPriority, QuestionStatus
from app.models import Question
from app.rate_limit import limiter, llm_limit
from app.schemas import DraftOut, DraftRequest, QuestionOut, QuestionPatch
from app.services.draft_message import draft_message

router = APIRouter(prefix="/api", tags=["questions"])

PRIORITY_ORDER = {QuestionPriority.HIGH: 0, QuestionPriority.MEDIUM: 1, QuestionPriority.LOW: 2}


@router.get("/projects/{project_id}/questions", response_model=list[QuestionOut])
async def list_questions(
    project_id: str,
    status: Optional[QuestionStatus] = QuestionStatus.OPEN,
    session: AsyncSession = Depends(get_db),
) -> list[Question]:
    await project_or_404(session, project_id)
    stmt = select(Question).where(Question.project_id == project_id)
    if status:
        stmt = stmt.where(Question.status == status)
    rows = (await session.execute(stmt)).scalars().all()
    return sorted(rows, key=lambda q: (PRIORITY_ORDER[q.priority], q.created_at))


@router.patch("/questions/{question_id}", response_model=QuestionOut)
async def patch_question(
    question_id: str, body: QuestionPatch, session: AsyncSession = Depends(get_db)
) -> Question:
    question = await session.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(question, field, value)
    await session.flush()
    return question


@router.post("/projects/{project_id}/draft-message", response_model=DraftOut)
@limiter.limit(llm_limit)
async def draft(
    request: Request,
    project_id: str,
    body: DraftRequest,
    session: AsyncSession = Depends(get_db),
    llm=Depends(get_llm),
) -> DraftOut:
    await project_or_404(session, project_id)
    stmt = select(Question).where(Question.project_id == project_id)
    if body.question_ids:
        stmt = stmt.where(Question.id.in_(body.question_ids))
        questions = list((await session.execute(stmt)).scalars())
        if len(questions) != len(set(body.question_ids)):
            raise HTTPException(status_code=404, detail="One or more questions were not found in this project.")
    else:
        stmt = stmt.where(Question.status == QuestionStatus.OPEN)
        questions = sorted((await session.execute(stmt)).scalars(), key=lambda q: (PRIORITY_ORDER[q.priority], q.created_at))[:8]
    try:
        text = await draft_message(llm, questions, body.language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return DraftOut(language=body.language, text=text, question_ids=[q.id for q in questions])
