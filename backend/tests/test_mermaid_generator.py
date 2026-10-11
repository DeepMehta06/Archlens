"""
Unit tests for deterministic Mermaid compilation and dangling-reference handling.
"""
from app.diagram_specs import (
    ArchitectureDiagramSpec,
    ERDiagramSpec,
    RequirementTraceabilitySpec,
    SequenceDiagramSpec,
)
from app.services.mermaid_generator import (
    dangling_references,
    generate_architecture_mermaid,
    generate_er_mermaid,
    generate_requirements_mermaid,
    generate_sequence_mermaid,
)


def test_flowchart_drops_edges_to_undefined_nodes():
    spec = ArchitectureDiagramSpec.model_validate({
        "nodes": [{"id": "A", "label": "A"}, {"id": "B", "label": "B"}],
        "edges": [
            {"from": "A", "to": "B"},
            {"from": "B", "to": "int_001", "label": "x"},
            {"from": "missing", "to": "A"},
        ],
    })

    source = generate_architecture_mermaid(spec)

    assert "a --> b" in source
    assert "int_001" not in source
    assert "missing" not in source
    assert dangling_references(spec) == ["B -> int_001", "missing -> A"]


def test_references_resolve_after_id_sanitising():
    spec = ArchitectureDiagramSpec.model_validate({
        "nodes": [{"id": "C-Frontend", "label": "UI"}, {"id": "c backend", "label": "API"}],
        "edges": [{"from": "c_frontend", "to": "C-Backend"}],
    })

    assert dangling_references(spec) == []
    assert "c_frontend --> c_backend" in generate_architecture_mermaid(spec)


def test_sequence_drops_messages_with_unknown_participants():
    spec = SequenceDiagramSpec.model_validate({
        "participants": [{"id": "U", "label": "User"}, {"id": "A", "label": "API"}],
        "messages": [
            {"from": "U", "to": "A", "action": "login"},
            {"from": "A", "to": "DB", "action": "query"},
        ],
    })

    source = generate_sequence_mermaid(spec)

    assert "u->>a: login" in source
    assert "query" not in source
    assert dangling_references(spec) == ["A -> DB"]


def test_er_drops_relationships_to_unknown_entities():
    spec = ERDiagramSpec.model_validate({
        "entities": [{"id": "E1", "name": "User", "attributes": ["email"]}],
        "relationships": [{"from": "E1", "to": "E9", "cardinality": "one-to-many", "label": "owns"}],
    })

    source = generate_er_mermaid(spec)

    assert "owns" not in source
    assert "E9" not in source
    assert dangling_references(spec) == ["E1 -> E9"]


def test_traceability_drops_links_to_undefined_requirements_or_components():
    spec = RequirementTraceabilitySpec.model_validate({
        "requirements": [{"id": "FR-001", "label": "Login"}],
        "components": [{"id": "C1", "label": "API"}],
        "links": [
            {"requirement": "FR-001", "component": "C1"},
            {"requirement": "FR-001", "component": "c_notionadapter"},
            {"requirement": "FR-099", "component": "C1"},
        ],
    })

    source = generate_requirements_mermaid(spec)

    assert source.count("satisfies") == 1
    assert "c1 - satisfies -> fr_001" in source
    assert "notionadapter" not in source
    assert "fr_099" not in source
    assert dangling_references(spec) == [
        "c_notionadapter satisfies FR-001",
        "C1 satisfies FR-099",
    ]


def test_labels_with_quotes_and_unsafe_characters_cannot_break_the_diagram():
    arch = ArchitectureDiagramSpec.model_validate({
        "nodes": [{"id": "A", "label": 'The "main" API'}, {"id": "B", "label": "DB"}],
        "edges": [{"from": "A", "to": "B", "label": 'reads "rows"'}],
    })
    seq = SequenceDiagramSpec.model_validate({
        "participants": [{"id": "U", "label": "User"}, {"id": "A", "label": "API"}],
        "messages": [{"from": "U", "to": "A", "action": "login; then #1 retry"}],
    })
    er = ERDiagramSpec.model_validate({
        "entities": [{"id": "E1", "name": "User", "attributes": ["id (PK)", "e mail"]}],
        "relationships": [],
    })

    assert '"The \'main\' API"' in generate_architecture_mermaid(arch)
    assert "login, then No.1 retry" in generate_sequence_mermaid(seq)
    er_source = generate_er_mermaid(er)
    assert "string id__PK" in er_source or "string id_PK" in er_source
    assert "(" not in er_source.split("{", 1)[1]


def test_clean_specs_report_nothing_dangling():
    spec = SequenceDiagramSpec.model_validate({
        "participants": [{"id": "U", "label": "User"}, {"id": "A", "label": "API"}],
        "messages": [{"from": "U", "to": "A", "action": "go"}],
    })

    assert dangling_references(spec) == []
