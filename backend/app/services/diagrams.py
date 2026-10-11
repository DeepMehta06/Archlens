"""Diagram generation: the model fills a structured spec, code compiles and checks the Mermaid."""
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.diagram_specs import (
    ArchitectureDiagramSpec,
    ComponentDiagramSpec,
    ERDiagramSpec,
    RequirementTraceabilitySpec,
    SequenceDiagramSpec,
)
from app.enums import ApprovalStatus
from app.models import Diagram, LedgerItem
from app.services.mermaid_generator import (
    dangling_references,
    generate_architecture_mermaid,
    generate_component_mermaid,
    generate_er_mermaid,
    generate_requirements_mermaid,
    generate_sequence_mermaid,
)
from app.services.prompts import load_prompt
from app.validators.mermaid_validator import validate_mermaid

MAX_ITEMS = 40

SPECS = {
    "architecture": (ArchitectureDiagramSpec, generate_architecture_mermaid),
    "component": (ComponentDiagramSpec, generate_component_mermaid),
    "sequence": (SequenceDiagramSpec, generate_sequence_mermaid),
    "er": (ERDiagramSpec, generate_er_mermaid),
    "requirements": (RequirementTraceabilitySpec, generate_requirements_mermaid),
}


class NothingToDraw(ValueError):
    pass


async def generate_diagram(
    session: AsyncSession,
    llm: Any,
    project_id: str,
    diagram_type: str,
    focus: Optional[str] = None,
) -> Diagram:
    if diagram_type not in SPECS:
        raise ValueError(f"Unsupported diagram type: {diagram_type}")
    items = list(
        (
            await session.execute(
                select(LedgerItem)
                .where(
                    LedgerItem.project_id == project_id,
                    LedgerItem.active.is_(True),
                    LedgerItem.approval_status != ApprovalStatus.REJECTED,
                )
                .order_by(LedgerItem.display_id)
                .limit(MAX_ITEMS)
            )
        ).scalars()
    )
    if not items:
        raise NothingToDraw("The ledger has no items yet, so there is nothing to draw.")

    spec_cls, compile_spec = SPECS[diagram_type]
    ledger_lines = [
        f"{i.display_id} [{i.item_type.value}|{i.evidence_status.value}] {i.title}: {i.description}"
        for i in items
    ]
    user = f"DIAGRAM KIND: {diagram_type}\n" + (f"FOCUS: {focus}\n" if focus else "") + "LEDGER:\n" + "\n".join(ledger_lines)
    spec = await llm.chat_json(
        [{"role": "system", "content": load_prompt("diagram_spec")}, {"role": "user", "content": user}],
        spec_cls,
        stage="diagram",
        temperature=0.2,
        think=False,
    )
    source = compile_spec(spec)
    validation = validate_mermaid(source)
    warnings = list(validation.errors)
    dropped = dangling_references(spec)
    if dropped:
        warnings.append(
            f"Dropped {len(dropped)} reference(s) to items the model never defined: " + "; ".join(dropped)
        )
    diagram = Diagram(
        project_id=project_id,
        diagram_type=diagram_type,
        title=f"{diagram_type.capitalize()} diagram",
        mermaid_source=source,
        spec_json=spec.model_dump(by_alias=True),
        warnings_json=warnings,
    )
    session.add(diagram)
    await session.flush()
    return diagram
