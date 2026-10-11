"""Project-scoped chat orchestrator.

A schema-constrained router picks an intent; code dispatches to the same service functions
the REST API uses. Answers are streamed from retrieved context only, citation markers are
validated against what was actually supplied, and state changes (approvals, snapshots) are
never made from chat. The server fixes the project id; the model never supplies one.
"""
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.enums import ApprovalStatus, ChatRole, QuestionPriority, QuestionStatus
from app.logging_config import get_logger
from app.models import ChatMessage, ChatThread, LedgerItem, Project, Question, ScopeSnapshot
from app.schemas import ReformulateOutput, RouterOutput
from app.services import ledger
from app.services.change_detection import compare_request
from app.services.diagrams import NothingToDraw, generate_diagram
from app.services.draft_message import draft_message
from app.services.embeddings import EmbeddingService
from app.services.hybrid_retrieval import Retriever
from app.services.ollama_client import OllamaBadResponse, OllamaError
from app.services.prompts import load_prompt
from app.services.whatsapp_parser import parse_whatsapp

logger = get_logger(__name__)

HISTORY_TURNS = 6
LONG_PASTE_CHARS = 800
MAX_LIST_ITEMS = 30
MAX_DRAFT_QUESTIONS = 8
PASSAGE_CHARS = 700
MAX_QUERY_REFORMULATIONS = 1
MARKER = re.compile(r"\[([CL]\d+)\]")
PRIORITY_ORDER = {QuestionPriority.HIGH: 0, QuestionPriority.MEDIUM: 1, QuestionPriority.LOW: 2}

OFF_TOPIC_REPLY = (
    "I can only help with this project: what the client said, the scope ledger, open questions, "
    "diagrams and change requests. For example, ask what the client said about payments."
)


@dataclass
class ChatDeps:
    session_factory: async_sessionmaker[AsyncSession]
    llm: Any
    retriever: Retriever
    embedder: EmbeddingService


@dataclass
class TurnState:
    text: str = ""
    cards: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    grounded: Optional[bool] = None


def _say(state: TurnState, text: str) -> dict[str, Any]:
    state.text += text
    return {"type": "token", "text": text}


def _card(state: TurnState, card: dict[str, Any]) -> dict[str, Any]:
    state.cards.append(card)
    return {"type": "card", "card": card}


async def get_or_create_thread(
    session: AsyncSession, project_id: str, thread_id: Optional[str]
) -> ChatThread:
    if thread_id:
        thread = await session.get(ChatThread, thread_id)
        if thread is None or thread.project_id != project_id:
            raise LookupError("Chat thread not found in this project.")
        return thread
    existing = (
        await session.execute(
            select(ChatThread).where(ChatThread.project_id == project_id).order_by(ChatThread.created_at).limit(1)
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    thread = ChatThread(project_id=project_id)
    session.add(thread)
    await session.flush()
    return thread


async def recent_history(session: AsyncSession, thread_id: str, before_id: str) -> list[dict[str, str]]:
    rows = (
        await session.execute(
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread_id, ChatMessage.id != before_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(HISTORY_TURNS)
        )
    ).scalars()
    return [{"role": m.role.value, "content": m.content} for m in reversed(list(rows))]


async def route(llm: Any, message: str) -> RouterOutput:
    messages = [
        {"role": "system", "content": load_prompt("router")},
        {"role": "user", "content": message[:2000]},
    ]
    try:
        return await llm.chat_json(messages, RouterOutput, stage="router", temperature=0.0, think=False)
    except OllamaBadResponse:
        return RouterOutput(intent="answer_question", query=message)


async def _reformulate_query(llm: Any, question: str, failed_query: str) -> Optional[str]:
    messages = [
        {"role": "system", "content": load_prompt("reformulate_query")},
        {
            "role": "user",
            "content": f"ORIGINAL QUESTION: {question[:500]}\nSEARCH QUERY THAT FOUND NOTHING: {failed_query[:300]}",
        },
    ]
    try:
        result = await llm.chat_json(messages, ReformulateOutput, stage="reformulate_query", temperature=0.0, think=False)
    except OllamaBadResponse:
        return None
    if result.give_up or not result.query:
        return None
    reformulated = result.query.strip()[:300]
    return reformulated or None


def _item_card(item: LedgerItem, open_questions: int) -> dict[str, Any]:
    out = ledger.to_item_out(item, open_questions)
    return {
        "id": out.id,
        "display_id": out.display_id,
        "title": out.title,
        "item_type": out.item_type.value,
        "evidence_status": out.evidence_status.value,
        "approval_status": out.approval_status.value,
        "stated_by": out.stated_by.value,
        "evidence_total": out.evidence_total,
        "evidence_verified": out.evidence_verified,
    }


async def _general_reasoning(
    deps: ChatDeps,
    session: AsyncSession,
    project: Project,
    message: str,
    history: list[dict[str, str]],
    state: TurnState,
) -> AsyncIterator[dict[str, Any]]:
    """Answer broad / meta questions using a project summary instead of retrieval."""
    yield {"type": "status", "stage": "thinking"}

    # Build a concise project summary for context
    item_rows = list(
        (await session.execute(
            select(LedgerItem).where(
                LedgerItem.project_id == project.id,
                LedgerItem.active.is_(True),
            )
        )).scalars()
    )
    approved = sum(i.approval_status == ApprovalStatus.APPROVED for i in item_rows)
    needs_review = sum(i.approval_status == ApprovalStatus.NEEDS_REVIEW for i in item_rows)
    rejected = sum(i.approval_status == ApprovalStatus.REJECTED for i in item_rows)

    type_counts: dict[str, int] = {}
    for i in item_rows:
        t = i.item_type.value if hasattr(i.item_type, "value") else str(i.item_type)
        type_counts[t] = type_counts.get(t, 0) + 1

    open_q = await _open_questions(session, project.id)
    snapshot_rows = list(
        (await session.execute(
            select(ScopeSnapshot).where(ScopeSnapshot.project_id == project.id)
        )).scalars()
    )

    summary_parts = [
        f"Project name: {project.name}",
        f"Description: {project.description or 'not set'}",
        f"Ledger items: {len(item_rows)} total ({approved} approved, {needs_review} awaiting review, {rejected} rejected)",
        f"Item types: {', '.join(f'{v} {k}' for k, v in type_counts.items()) or 'none yet'}",
        f"Open questions: {len(open_q)}",
        f"Scope snapshots: {len(snapshot_rows)}",
    ]
    # Include a few item titles for flavour
    if item_rows:
        sample = item_rows[:10]
        summary_parts.append("Sample ledger items: " + "; ".join(f"{i.title} ({i.item_type.value})" for i in sample))

    project_summary = "\n".join(summary_parts)

    messages = [
        {"role": "system", "content": load_prompt("general_reasoning")},
        *history,
        {"role": "user", "content": f"PROJECT SUMMARY:\n{project_summary}\n\nQUESTION: {message}"},
    ]
    async for delta in deps.llm.stream_chat(messages, think=False, temperature=0.3):
        yield {"type": "token", "text": delta}
        state.text += delta
    state.grounded = True


async def _answer(
    deps: ChatDeps,
    session: AsyncSession,
    project_id: str,
    question: str,
    query: str,
    history: list[dict[str, str]],
    state: TurnState,
) -> AsyncIterator[dict[str, Any]]:
    yield {"type": "status", "stage": "searching"}
    found = await deps.retriever.search_chunks(session, project_id, query, top_k=6)
    item_hits = await deps.retriever.search_items(session, project_id, query, top_k=4)

    for _ in range(MAX_QUERY_REFORMULATIONS):
        if found.hits or item_hits:
            break
        yield {"type": "status", "stage": "reformulating"}
        reformulated = await _reformulate_query(deps.llm, question, query)
        if not reformulated or reformulated.casefold() == query.casefold():
            break
        query = reformulated
        yield {"type": "status", "stage": "searching"}
        found = await deps.retriever.search_chunks(session, project_id, query, top_k=6)
        item_hits = await deps.retriever.search_items(session, project_id, query, top_k=4)

    if not found.hits and not item_hits:
        yield _say(state, "I couldn't find anything about that in this project's sources.")
        return

    markers: dict[str, dict[str, Any]] = {}
    lines: list[str] = []
    for n, hit in enumerate(found.hits, start=1):
        marker = f"C{n}"
        label = hit.location.get("source_label") or "source"
        markers[marker] = {
            "marker": marker,
            "kind": "chunk",
            "chunk_id": hit.chunk_id,
            "source_id": hit.source_id,
            "source_label": label,
            "snippet": hit.text[:160],
        }
        lines.append(f"[{marker}] ({label}) {hit.text[:PASSAGE_CHARS]}")
    for n, hit in enumerate(item_hits, start=1):
        marker = f"L{n}"
        markers[marker] = {
            "marker": marker,
            "kind": "ledger_item",
            "ledger_item_id": hit.ledger_item_id,
            "display_id": hit.location.get("display_id"),
            "snippet": hit.text[:160],
        }
        lines.append(f"[{marker}] (ledger {hit.location.get('display_id')}) {hit.text[:PASSAGE_CHARS]}")

    yield {"type": "status", "stage": "writing", "retrieval_mode": found.mode}
    messages = [
        {"role": "system", "content": load_prompt("answer")},
        *history,
        {"role": "user", "content": "CONTEXT:\n" + "\n".join(lines) + f"\n\nQUESTION: {question}"},
    ]
    raw = ""
    async for delta in deps.llm.stream_chat(messages, think=False, temperature=0.2):
        raw += delta
        yield {"type": "token", "text": delta}

    used = list(dict.fromkeys(MARKER.findall(raw)))
    invalid = [m for m in used if m not in markers]
    cleaned = raw
    for marker in invalid:
        cleaned = cleaned.replace(f"[{marker}]", "")
    if cleaned != raw:
        yield {"type": "replace", "text": cleaned}
    state.text = cleaned
    state.citations = [markers[m] for m in used if m in markers]
    state.grounded = bool(state.citations)
    yield {"type": "citations", "citations": state.citations, "grounded": state.grounded}


async def _dispatch(
    deps: ChatDeps,
    session: AsyncSession,
    project: Project,
    message: str,
    history: list[dict[str, str]],
    state: TurnState,
) -> AsyncIterator[dict[str, Any]]:
    chat = parse_whatsapp(message)
    if len(message) > LONG_PASTE_CHARS or chat is not None:
        yield _say(state, "This looks like pasted conversation text. Do you want to add it as a source and analyze it?")
        yield _card(
            state,
            {
                "type": "confirm_add_source",
                "preview": message[:240],
                "char_count": len(message),
                "looks_like_whatsapp": chat is not None,
            },
        )
        return

    yield {"type": "status", "stage": "routing"}
    routed = await route(deps.llm, message)
    logger.info("chat_routed", intent=routed.intent)

    if routed.intent == "off_topic":
        yield _say(state, OFF_TOPIC_REPLY)

    elif routed.intent == "general_reasoning":
        async for event in _general_reasoning(deps, session, project, message, history, state):
            yield event

    elif routed.intent == "answer_question":
        async for event in _answer(deps, session, project.id, message, routed.query or message, history, state):
            yield event

    elif routed.intent == "list_ledger":
        stmt = select(LedgerItem).where(
            LedgerItem.project_id == project.id,
            LedgerItem.active.is_(True),
            LedgerItem.approval_status != ApprovalStatus.REJECTED,
        )
        items = list((await session.execute(stmt.order_by(LedgerItem.display_id))).scalars())
        if routed.query:
            needle = routed.query.casefold()
            filtered = [i for i in items if needle in f"{i.title} {i.description}".casefold()]
            items = filtered or items
        counts = await ledger.open_question_counts(session, project.id)
        approved = sum(i.approval_status == ApprovalStatus.APPROVED for i in items)
        yield _say(state, f"There are {len(items)} items in the ledger ({approved} approved, {len(items) - approved} awaiting review).")
        yield _card(state, {"type": "ledger_list", "items": [_item_card(i, counts.get(i.id, 0)) for i in items[:MAX_LIST_ITEMS]]})

    elif routed.intent == "open_questions":
        questions = await _open_questions(session, project.id)
        if not questions:
            yield _say(state, "There are no open questions right now.")
        else:
            yield _say(state, f"There are {len(questions)} open questions.")
            yield _card(state, _questions_card(questions))

    elif routed.intent == "draft_message":
        questions = (await _open_questions(session, project.id))[:MAX_DRAFT_QUESTIONS]
        if not questions:
            yield _say(state, "There are no open questions to write to the client about.")
        else:
            yield {"type": "status", "stage": "drafting"}
            language = routed.language or "english"
            text = await draft_message(deps.llm, questions, language)
            yield _say(state, f"Here is an editable {language} draft covering {len(questions)} open questions.")
            yield _card(
                state,
                {"type": "draft_message", "language": language, "text": text, "question_ids": [q.id for q in questions]},
            )

    elif routed.intent == "create_diagram":
        yield {"type": "status", "stage": "drawing"}
        try:
            diagram = await generate_diagram(session, deps.llm, project.id, routed.diagram_type or "architecture", routed.query)
        except NothingToDraw as exc:
            yield _say(state, str(exc))
        else:
            await session.commit()
            yield _say(state, f"I drew a {diagram.diagram_type} diagram from the current ledger.")
            yield _card(
                state,
                {
                    "type": "diagram",
                    "diagram_id": diagram.id,
                    "diagram_type": diagram.diagram_type,
                    "title": diagram.title,
                    "mermaid_source": diagram.mermaid_source,
                    "warnings": diagram.warnings_json or [],
                },
            )

    elif routed.intent == "compare_request":
        snapshot = (
            await session.execute(
                select(ScopeSnapshot)
                .where(ScopeSnapshot.project_id == project.id)
                .order_by(ScopeSnapshot.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if snapshot is None:
            yield _say(state, "There is no approved baseline yet. Approve items and create a snapshot first, then I can compare new requests against it.")
        else:
            yield {"type": "status", "stage": "comparing"}
            report = await compare_request(
                session,
                llm=deps.llm,
                retriever=deps.retriever,
                embedder=deps.embedder,
                project=project,
                snapshot=snapshot,
                incoming_text=routed.query or message,
            )
            await session.commit()
            results = report.results_json["results"]
            tally: dict[str, int] = {}
            for r in results:
                tally[r["classification"]] = tally.get(r["classification"], 0) + 1
            summary = ", ".join(_tally_label(c, n) for c, n in tally.items()) or "no scope-related claims"
            yield _say(state, f"Compared against {snapshot.label}: {summary}. New requests were filed as items to review, not approved.")
            yield _card(state, {"type": "change_report", "report_id": report.id, "snapshot_label": snapshot.label, "results": results})


TALLY_LABELS = {
    "already_covered": ("already covered", "already covered"),
    "new_requirement": ("new requirement", "new requirements"),
    "contradiction": ("contradiction", "contradictions"),
    "unclear": ("unclear", "unclear"),
}


def _tally_label(classification: str, count: int) -> str:
    singular, plural = TALLY_LABELS[classification]
    return f"{count} {singular if count == 1 else plural}"


async def _open_questions(session: AsyncSession, project_id: str) -> list[Question]:
    rows = (
        await session.execute(
            select(Question).where(Question.project_id == project_id, Question.status == QuestionStatus.OPEN)
        )
    ).scalars()
    return sorted(rows, key=lambda q: (PRIORITY_ORDER[q.priority], q.created_at))


def _questions_card(questions: list[Question]) -> dict[str, Any]:
    return {
        "type": "questions",
        "questions": [
            {"id": q.id, "question": q.question, "reason": q.reason, "priority": q.priority.value, "ledger_item_id": q.ledger_item_id}
            for q in questions
        ],
    }


async def run_turn(
    deps: ChatDeps, project_id: str, message: str, thread_id: Optional[str] = None
) -> AsyncIterator[dict[str, Any]]:
    async with deps.session_factory() as session:
        project = await session.get(Project, project_id)
        thread = await get_or_create_thread(session, project_id, thread_id)
        user_message = ChatMessage(thread_id=thread.id, project_id=project_id, role=ChatRole.USER, content=message)
        session.add(user_message)
        await session.commit()
        history = await recent_history(session, thread.id, user_message.id)
        yield {"type": "thread", "thread_id": thread.id, "user_message_id": user_message.id}

        state = TurnState()
        try:
            async for event in _dispatch(deps, session, project, message, history, state):
                yield event
        except OllamaError as exc:
            await session.rollback()
            state.text = state.text or f"The local model could not complete that: {exc}"
            state.cards.append({"type": "error", "message": str(exc)})
            yield {"type": "error", "message": str(exc)}
        except Exception:
            await session.rollback()
            logger.exception("chat_turn_failed", project_id=project_id)
            state.text = state.text or "Something went wrong while handling that. Check the server logs."
            state.cards.append({"type": "error", "message": "Unexpected error."})
            yield {"type": "error", "message": "Unexpected error."}

        assistant = ChatMessage(
            thread_id=thread.id,
            project_id=project_id,
            role=ChatRole.ASSISTANT,
            content=state.text,
            citations_json=state.citations or None,
            cards_json=state.cards or None,
        )
        session.add(assistant)
        await session.commit()
        yield {"type": "done", "message_id": assistant.id, "grounded": state.grounded}
