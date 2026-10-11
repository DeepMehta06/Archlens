"""
Deterministic Mermaid generators for compiling structured diagram specs into
raw Mermaid source code.

Edges, messages, relationships and traceability links that reference an id the
spec never defines are dropped: Mermaid either invents a ghost node for them or
fails to render the whole diagram. dangling_references() reports what was dropped.
"""

from typing import Union

from app.diagram_specs import (
    ArchitectureDiagramSpec,
    ComponentDiagramSpec,
    SequenceDiagramSpec,
    ERDiagramSpec,
    RequirementTraceabilitySpec
)

DiagramSpec = Union[
    ArchitectureDiagramSpec,
    ComponentDiagramSpec,
    SequenceDiagramSpec,
    ERDiagramSpec,
    RequirementTraceabilitySpec,
]


def _label(text: str) -> str:
    return " ".join(text.replace('"', "'").split())


def _action(text: str) -> str:
    return " ".join(text.replace(";", ",").replace("#", "No.").split())


def _attribute(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in text.strip())
    return cleaned.strip("_") or "field"


def _sanitize_id(identifier: str) -> str:
    """Sanitize IDs for Mermaid to prevent syntax errors."""
    return identifier.replace("-", "_").replace(" ", "_").lower()


def _known(items) -> set[str]:
    return {_sanitize_id(i.id) for i in items}


def _resolves(known: set[str], *identifiers: str) -> bool:
    return all(_sanitize_id(i) in known for i in identifiers)


def dangling_references(spec: DiagramSpec) -> list[str]:
    """Describe every relation in the spec that points at an undefined id."""
    found: list[str] = []
    if isinstance(spec, (ArchitectureDiagramSpec, ComponentDiagramSpec)):
        known = _known(spec.nodes)
        found = [f"{e.from_node} -> {e.to_node}" for e in spec.edges
                 if not _resolves(known, e.from_node, e.to_node)]
    elif isinstance(spec, SequenceDiagramSpec):
        known = _known(spec.participants)
        found = [f"{m.from_node} -> {m.to_node}" for m in spec.messages
                 if not _resolves(known, m.from_node, m.to_node)]
    elif isinstance(spec, ERDiagramSpec):
        known = _known(spec.entities)
        found = [f"{r.from_node} -> {r.to_node}" for r in spec.relationships
                 if not _resolves(known, r.from_node, r.to_node)]
    elif isinstance(spec, RequirementTraceabilitySpec):
        reqs, comps = _known(spec.requirements), _known(spec.components)
        found = [f"{link.component} satisfies {link.requirement}" for link in spec.links
                 if not (_resolves(reqs, link.requirement) and _resolves(comps, link.component))]
    return found


def _flowchart(spec: Union[ArchitectureDiagramSpec, ComponentDiagramSpec]) -> str:
    known = _known(spec.nodes)
    lines = ["flowchart TD"]
    for node in spec.nodes:
        node_id = _sanitize_id(node.id)
        lines.append(f'    {node_id}["{_label(node.label)}"]')

    for edge in spec.edges:
        if not _resolves(known, edge.from_node, edge.to_node):
            continue
        from_id = _sanitize_id(edge.from_node)
        to_id = _sanitize_id(edge.to_node)
        if edge.label:
            lines.append(f'    {from_id} -->|"{_label(edge.label)}"| {to_id}')
        else:
            lines.append(f'    {from_id} --> {to_id}')

    return "\n".join(lines)


def generate_architecture_mermaid(spec: ArchitectureDiagramSpec) -> str:
    return _flowchart(spec)


def generate_component_mermaid(spec: ComponentDiagramSpec) -> str:
    return _flowchart(spec)


def generate_sequence_mermaid(spec: SequenceDiagramSpec) -> str:
    known = _known(spec.participants)
    lines = ["sequenceDiagram"]
    for p in spec.participants:
        p_id = _sanitize_id(p.id)
        lines.append(f'    participant {p_id} as {_label(p.label)}')

    for msg in spec.messages:
        if not _resolves(known, msg.from_node, msg.to_node):
            continue
        from_id = _sanitize_id(msg.from_node)
        to_id = _sanitize_id(msg.to_node)
        lines.append(f'    {from_id}->>{to_id}: {_action(msg.action)}')

    return "\n".join(lines)


def generate_er_mermaid(spec: ERDiagramSpec) -> str:
    known = _known(spec.entities)
    lines = ["erDiagram"]
    for entity in spec.entities:
        e_id = _sanitize_id(entity.id).upper()
        lines.append(f'    {e_id} {{')
        for attr in entity.attributes:
            lines.append(f'        string {_attribute(attr)}')
        lines.append('    }')

    for rel in spec.relationships:
        if not _resolves(known, rel.from_node, rel.to_node):
            continue
        from_id = _sanitize_id(rel.from_node).upper()
        to_id = _sanitize_id(rel.to_node).upper()

        # Determine mermaid relationship symbols based on cardinality string
        # Default to one-to-many if unknown
        card = rel.cardinality.lower().strip()
        rel_symbol = "||--o{"
        if card in ["one-to-one", "1:1", "one to one"]:
            rel_symbol = "||--||"
        elif card in ["many-to-many", "n:n", "m:n", "many to many"]:
            rel_symbol = "}o--o{"

        lines.append(f'    {from_id} {rel_symbol} {to_id} : "{_label(rel.label)}"')

    return "\n".join(lines)


def generate_requirements_mermaid(spec: RequirementTraceabilitySpec) -> str:
    reqs, comps = _known(spec.requirements), _known(spec.components)
    lines = ["requirementDiagram"]
    for req in spec.requirements:
        req_id = _sanitize_id(req.id)
        lines.append(f'    requirement {req_id} {{')
        lines.append(f'        id: "{req.id}"')
        lines.append(f'        text: "{_label(req.label)}"')
        lines.append('    }')

    for comp in spec.components:
        comp_id = _sanitize_id(comp.id)
        lines.append(f'    element {comp_id} {{')
        lines.append(f'        type: "{comp.type or "component"}"')
        lines.append('    }')

    for link in spec.links:
        if not (_resolves(reqs, link.requirement) and _resolves(comps, link.component)):
            continue
        req_id = _sanitize_id(link.requirement)
        comp_id = _sanitize_id(link.component)
        lines.append(f'    {comp_id} - satisfies -> {req_id}')

    return "\n".join(lines)
