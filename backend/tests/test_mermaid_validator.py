"""
Unit tests for Mermaid validation.
"""
import pytest
from app.validators.mermaid_validator import validate_mermaid, clean_mermaid_source, ValidationResult


class TestMermaidValidation:

    def test_valid_flowchart(self):
        source = """flowchart LR
    User --> Frontend
    Frontend --> API
    API --> Database"""
        result = validate_mermaid(source)
        assert result.is_valid is True
        assert result.diagram_type == "flowchart"

    def test_valid_sequence_diagram(self):
        source = """sequenceDiagram
    User->>Frontend: Request
    Frontend->>API: POST /data
    API-->>Frontend: Response
    Frontend-->>User: Display"""
        result = validate_mermaid(source)
        assert result.is_valid is True
        assert result.diagram_type == "sequenceDiagram"

    def test_valid_er_diagram(self):
        source = """erDiagram
    USER {
        string id
        string email
        string name
    }
    DOCUMENT {
        string id
        string title
    }
    USER ||--o{ DOCUMENT : "uploads" """
        result = validate_mermaid(source)
        assert result.is_valid is True
        assert result.diagram_type == "erDiagram"

    def test_valid_requirement_diagram(self):
        source = """requirementDiagram
    requirement FR_001 {
        id: FR-001
        text: Users can upload documents
        risk: high
        verifyMethod: test
    }
    element UploadService {
        type: component
    }
    FR_001 - satisfies -> UploadService"""
        result = validate_mermaid(source)
        assert result.is_valid is True

    def test_empty_source(self):
        result = validate_mermaid("")
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_unknown_diagram_type(self):
        source = "invalidType\n    A --> B"
        result = validate_mermaid(source)
        assert result.is_valid is False
        assert any("Unknown" in e or "missing" in e for e in result.errors)

    def test_mismatched_subgraph(self):
        source = """flowchart LR
    subgraph Frontend
        A --> B
    A --> C"""
        result = validate_mermaid(source)
        # Should detect mismatch
        assert any("subgraph" in e.lower() or "end" in e.lower() for e in result.errors)

    def test_markdown_fences_stripped(self):
        source = """```mermaid
flowchart LR
    A --> B
```"""
        result = validate_mermaid(source)
        # Should strip fences and detect flowchart
        assert result.diagram_type == "flowchart"

    def test_clean_mermaid_removes_fences(self):
        source = "```mermaid\nflowchart LR\n    A --> B\n```"
        cleaned = clean_mermaid_source(source)
        assert "```" not in cleaned
        assert cleaned.startswith("flowchart")

    def test_too_short(self):
        result = validate_mermaid("flowchart LR")
        assert result.is_valid is False


class TestMermaidWarnings:

    def test_quoted_flowchart_labels_and_arrows_raise_no_warnings(self):
        source = '''flowchart TD
    c_ui["Web UI (React)"]
    c_api["API Server"]
    c_ui -->|"Request/Display"| c_api
    c_api -.-> c_ui
    c_api ==> c_ui'''
        result = validate_mermaid(source)
        assert result.is_valid is True
        assert result.errors == []

    def test_sequence_arrows_raise_no_warnings(self):
        source = '''sequenceDiagram
    participant u as User
    u->>u: think
    u-->>u: done'''
        assert validate_mermaid(source).errors == []

    def test_chained_nodes_on_one_line_raise_no_warnings(self):
        source = '''flowchart LR
    A["x"] --> B["y"] --> C["z"]'''
        assert validate_mermaid(source).errors == []

    def test_end_inside_a_label_is_not_a_subgraph_close(self):
        source = '''flowchart TD
    subgraph one
        a["front end"]
    end'''
        assert validate_mermaid(source).errors == []

    def test_odd_number_of_quotes_is_flagged(self):
        result = validate_mermaid('flowchart TD\n    a["broken]\n    a --> b')
        assert any("Unclosed quote" in e for e in result.errors)

    def test_angle_brackets_inside_label_are_flagged(self):
        result = validate_mermaid('flowchart TD\n    a["List<T> items"]\n    a --> b')
        assert any("Unescaped" in e for e in result.errors)

    def test_line_break_tag_inside_label_is_allowed(self):
        result = validate_mermaid('flowchart TD\n    a["two<br/>lines"]\n    a --> b')
        assert not any("Unescaped" in e for e in result.errors)

    def test_angle_brackets_in_sequence_message_text_are_flagged(self):
        result = validate_mermaid("sequenceDiagram\n    A->>B: send <payload>")
        assert any("Unescaped" in e for e in result.errors)

    def test_nested_brackets_in_unquoted_label_are_flagged(self):
        result = validate_mermaid("flowchart TD\n    a[outer [inner]]\n    a --> b")
        assert any("Nested brackets" in e for e in result.errors)

    def test_compiled_diagrams_raise_no_warnings(self):
        from app.diagram_specs import (
            ArchitectureDiagramSpec,
            ERDiagramSpec,
            SequenceDiagramSpec,
        )
        from app.services.mermaid_generator import (
            generate_architecture_mermaid,
            generate_er_mermaid,
            generate_sequence_mermaid,
        )

        arch = ArchitectureDiagramSpec.model_validate({
            "nodes": [{"id": "C1", "label": "Web UI (React)"}, {"id": "C2", "label": "API"}],
            "edges": [{"from": "C1", "to": "C2", "label": "Request/Display"}],
        })
        seq = SequenceDiagramSpec.model_validate({
            "participants": [{"id": "U", "label": "User"}, {"id": "A", "label": "API"}],
            "messages": [{"from": "U", "to": "A", "action": "login"}],
        })
        er = ERDiagramSpec.model_validate({
            "entities": [{"id": "E1", "name": "User", "attributes": ["email"]}],
            "relationships": [],
        })
        for source in (
            generate_architecture_mermaid(arch),
            generate_sequence_mermaid(seq),
            generate_er_mermaid(er),
        ):
            assert validate_mermaid(source).errors == [], source


class TestMermaidCleaning:

    def test_strips_json_fences(self):
        source = "```json\n{}\n```"
        cleaned = clean_mermaid_source(source)
        assert "```" not in cleaned

    def test_strips_plain_fences(self):
        source = "```\nflowchart LR\n```"
        cleaned = clean_mermaid_source(source)
        assert "```" not in cleaned

    def test_strips_whitespace(self):
        source = "\n\n  flowchart LR\n    A --> B\n\n"
        cleaned = clean_mermaid_source(source)
        assert cleaned.startswith("flowchart")
        assert not cleaned.endswith("\n")
