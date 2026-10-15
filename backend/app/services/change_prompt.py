"""Turns an approved/candidate ledger item into a brief a developer can hand to their own
coding agent, grounded in the item's real evidence and in code actually retrieved from a
connected repository -- never in file paths the model invented.

The model never sees real file paths. Affected files are given to it only as [F#] markers; any
marker it writes that was not supplied is stripped, and the markers it does use are substituted
for the real path afterwards, in code, the same discipline the chat assistant's [C#]/[L#]
citations already use. This also means ArchLens never writes to or opens anything in the repo --
this is the terminal, read-only output of the whole pipeline; a human decides what happens next.
"""
import re
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import SourceType
from app.models import LedgerItem, Source
from app.services.hybrid_retrieval import Retriever
from app.services.prompts import load_prompt

MARKER = re.compile(r"\[F(\d+)\]")
MAX_CODE_HITS = 8
SNIPPET_CHARS = 400

TARGET_PREAMBLES: dict[str, str] = {
    "generic": "Audience: a general-purpose AI coding assistant with no special conventions assumed.",
    "claude_code": (
        "Audience: Claude Code, a CLI coding agent that can open, read and edit files directly by "
        "path and run shell commands -- phrase steps as direct instructions."
    ),
    "cursor": (
        "Audience: Cursor's AI chat, working inside an open IDE workspace -- phrase steps as direct "
        "instructions."
    ),
    "github_copilot": (
        "Audience: GitHub Copilot Chat -- keep steps short and incremental, it works best that way."
    ),
}


class NoLedgerItem(Exception):
    pass


class NoRepositoryConnected(Exception):
    pass


class ChangePromptResult(BaseModel):
    prompt: str
    target: str
    affected_files: list[dict[str, Any]]


async def _has_connected_repo(session: AsyncSession, project_id: str) -> bool:
    row = (
        await session.execute(
            select(Source.id).where(Source.project_id == project_id, Source.source_type == SourceType.GITHUB_REPO).limit(1)
        )
    ).first()
    return row is not None


async def build_change_prompt(
    session: AsyncSession,
    llm: Any,
    retriever: Retriever,
    item_id: str,
    target: str = "generic",
) -> ChangePromptResult:
    item = await session.get(LedgerItem, item_id)
    if item is None:
        raise NoLedgerItem(f"Ledger item {item_id} was not found.")
    project_id = item.project_id

    if not await _has_connected_repo(session, project_id):
        raise NoRepositoryConnected(
            "No GitHub repository is connected to this project yet. "
            "Connect one with POST /projects/{id}/sources/github first."
        )

    query = f"{item.title}. {item.description}"
    code = await retriever.search_chunks(session, project_id, query, top_k=MAX_CODE_HITS, include_code=True)

    markers: dict[str, dict[str, Any]] = {}
    lines: list[str] = []
    for n, hit in enumerate(code.hits, start=1):
        marker = f"F{n}"
        location = hit.location or {}
        path = location.get("file_path", "unknown file")
        start, end = location.get("start_line"), location.get("end_line")
        markers[marker] = {"file_path": path, "start_line": start, "end_line": end}
        lines.append(f"[{marker}] {path} (lines {start}-{end}):\n{hit.text[:SNIPPET_CHARS]}")

    evidence_lines = [
        f'- "{e.quote}" ({e.speaker or e.speaker_role.value}) [{e.verification_status.value}]'
        for e in item.evidence_links
        if e.quote
    ]

    preamble = TARGET_PREAMBLES.get(target, TARGET_PREAMBLES["generic"])
    user_content = (
        f"REQUIREMENT: {item.title}\n{item.description}\n\n"
        f"EVIDENCE:\n{chr(10).join(evidence_lines) or '(none recorded)'}\n\n"
        f"CANDIDATE AFFECTED FILES:\n{(chr(10) + chr(10)).join(lines) or '(none found)'}\n\n"
        f"{preamble}"
    )
    messages = [
        {"role": "system", "content": load_prompt("change_prompt")},
        {"role": "user", "content": user_content},
    ]
    result = await llm.chat(messages, temperature=0.3, think=False, stage="change_prompt")
    raw = result.content.strip()
    if not raw:
        raise ValueError("The model returned an empty brief; try again.")

    used = {f"F{n}" for n in MARKER.findall(raw)}
    cleaned = raw
    for marker in used:
        if marker not in markers:
            cleaned = cleaned.replace(f"[{marker}]", "")
        else:
            loc = markers[marker]
            cleaned = cleaned.replace(f"[{marker}]", f"{loc['file_path']}:{loc['start_line']}-{loc['end_line']}")

    affected = [m for key, m in markers.items() if key in used]
    return ChangePromptResult(prompt=cleaned, target=target, affected_files=affected)
