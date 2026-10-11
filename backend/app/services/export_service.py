"""Markdown scope brief. Built from stored data only: the model is not involved."""
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import ApprovalStatus, QuestionStatus
from app.models import LedgerItem, Project, Question, ScopeSnapshot
from app.services.snapshots import serialize_item

TYPE_TITLES = {
    "requirement": "Requirements",
    "constraint": "Constraints",
    "decision": "Decisions",
    "assumption": "Assumptions",
}


def _evidence_lines(evidence: list[dict]) -> list[str]:
    lines = []
    for e in evidence:
        quote = (e.get("quote") or "").replace("\n", " / ")
        who = f" ({e['speaker']})" if e.get("speaker") else ""
        lines.append(f'  - Evidence{who}: "{quote}" [{e.get("verification_status", "unverified")}]')
    return lines


def _item_block(item: dict) -> list[str]:
    head = (
        f"- **{item['display_id']} {item['title']}** ({item['evidence_status']}, "
        f"risk {item['risk_level']}, stated by {item['stated_by']}): {item['description']}"
    )
    return [head, *_evidence_lines(item.get("evidence", []))]


async def build_markdown(session: AsyncSession, project: Project) -> str:
    snapshot = (
        await session.execute(
            select(ScopeSnapshot)
            .where(ScopeSnapshot.project_id == project.id)
            .order_by(ScopeSnapshot.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    items = list(
        (
            await session.execute(
                select(LedgerItem).where(LedgerItem.project_id == project.id).order_by(LedgerItem.display_id)
            )
        ).scalars()
    )
    questions = list(
        (
            await session.execute(
                select(Question)
                .where(Question.project_id == project.id, Question.status == QuestionStatus.OPEN)
                .order_by(Question.created_at)
            )
        ).scalars()
    )
    display_by_id = {i.id: i.display_id for i in items}

    out = [
        f"# Scope brief: {project.name}",
        "",
        f"_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC with local Gemma inference. "
        "Extracted items are candidates until a person approves them. This is not a legal contract._",
        "",
    ]

    if snapshot:
        out += [f"## Approved scope baseline: {snapshot.label} (version {snapshot.version})", ""]
        grouped = defaultdict(list)
        for entry in snapshot.snapshot_json["items"]:
            grouped[entry["item_type"]].append(entry)
        for kind, title in TYPE_TITLES.items():
            if grouped.get(kind):
                out += [f"### {title}", ""]
                for entry in grouped[kind]:
                    out += _item_block(entry)
                out.append("")
    else:
        out += ["## Approved scope baseline", "", "_No approved baseline yet. Approve items and create a snapshot._", ""]

    out += ["## Open questions", ""]
    if questions:
        for q in questions:
            ref = f" ({display_by_id[q.ledger_item_id]})" if q.ledger_item_id in display_by_id else ""
            out.append(f"- [{q.priority.value}] {q.question}{ref}: {q.reason}")
    else:
        out.append("_None._")
    out.append("")

    pending = [i for i in items if i.approval_status == ApprovalStatus.NEEDS_REVIEW and i.active]
    out += ["## Awaiting review", ""]
    if pending:
        for item in pending:
            out += _item_block(serialize_item(item))
    else:
        out.append("_None._")
    out.append("")

    rejected = [i for i in items if i.approval_status == ApprovalStatus.REJECTED]
    out += ["## Excluded (rejected)", ""]
    if rejected:
        out += [f"- **{i.display_id} {i.title}**: {i.description}" for i in rejected]
    else:
        out.append("_None._")
    out += [
        "",
        "## How to read this brief",
        "",
        "- **verified**: the quoted words were rebuilt from the original message and checked in code.",
        "- **explicit / tentative / inferred / unknown**: how firmly the source states it. A hedge such as "
        '"shayad" or "maybe" lowers an item to tentative.',
        "- **stated by**: whether the client or you said it, when the chat sender is known.",
        "",
    ]
    return "\n".join(out)
