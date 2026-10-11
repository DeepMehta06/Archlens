"""
Mermaid Diagram Validator.

Validates Mermaid source code by checking syntax patterns.
Uses pattern-based validation as a lightweight alternative to running
the full Mermaid JS parser server-side.

The frontend performs full rendering validation. The backend performs
structural validation to catch obvious issues before sending to the client.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str]
    diagram_type: Optional[str] = None


# Diagram type detection patterns
DIAGRAM_STARTERS = {
    "flowchart": r"^flowchart\s+(LR|TD|TB|RL|BT)",
    "sequenceDiagram": r"^sequenceDiagram",
    "erDiagram": r"^erDiagram",
    "requirementDiagram": r"^requirementDiagram",
    "classDiagram": r"^classDiagram",
    "stateDiagram": r"^stateDiagram",
    "gantt": r"^gantt",
    "pie": r"^pie",
    "graph": r"^graph\s+(LR|TD|TB|RL|BT)",
    "C4Context": r"^C4Context",
}

MIN_DIAGRAM_LINES = 2

_QUOTED = re.compile(r'"[^"]*"')
_LINE_BREAK_TAG = re.compile(r"<br\s*/?>", re.IGNORECASE)
_NESTED_BRACKET = re.compile(r"\[[^\[\]]*\[")


def _label_text(line: str, detected_type: Optional[str]) -> list[str]:
    """Text of a line that is label content, where < and > are not syntax."""
    labels = [m[1:-1] for m in _QUOTED.findall(line)]
    if detected_type == "sequenceDiagram" and ":" in line:
        labels.append(line.split(":", 1)[1])
    return [_LINE_BREAK_TAG.sub("", label) for label in labels]


def _line_warnings(lines: list[str], detected_type: Optional[str]) -> list[str]:
    warnings: list[str] = []
    for line in lines:
        if line.count('"') % 2 == 1:
            warnings.append("Unclosed quote in diagram")
        if any(re.search(r"[<>]", label) for label in _label_text(line, detected_type)):
            warnings.append("Unescaped < or > characters (use HTML entities or avoid)")
        if _NESTED_BRACKET.search(_QUOTED.sub("", line)):
            warnings.append("Nested brackets in node labels may cause parse errors")
    return list(dict.fromkeys(warnings))


def validate_mermaid(source: str) -> ValidationResult:
    """
    Validate Mermaid source code.

    Performs structural validation:
    1. Checks for known diagram type declaration
    2. Checks minimum content
    3. Checks for common syntax error patterns
    4. Checks for matching brackets/braces in flowcharts

    Args:
        source: Mermaid source code (without markdown fences).

    Returns:
        ValidationResult indicating validity and any errors.
    """
    if not source or not source.strip():
        return ValidationResult(
            is_valid=False,
            errors=["Diagram source is empty"],
        )

    source = source.strip()
    errors = []

    # Remove markdown fences if accidentally included
    if source.startswith("```"):
        source = re.sub(r"^```(?:mermaid)?\s*\n?", "", source)
        source = re.sub(r"\n?```\s*$", "", source)
        source = source.strip()
        errors.append(
            "Warning: Diagram contained markdown code fences which were stripped"
        )

    lines = [l for l in source.split("\n") if l.strip()]

    if len(lines) < MIN_DIAGRAM_LINES:
        return ValidationResult(
            is_valid=False,
            errors=["Diagram is too short to be valid"],
        )

    # Detect diagram type
    detected_type = None
    first_line = lines[0].strip()
    for dtype, pattern in DIAGRAM_STARTERS.items():
        if re.match(pattern, first_line, re.IGNORECASE):
            detected_type = dtype
            break

    if detected_type is None:
        errors.append(
            f"Unknown or missing diagram type declaration. "
            f"First line: '{first_line}'. "
            f"Expected: flowchart, sequenceDiagram, erDiagram, requirementDiagram, etc."
        )

    # Check for unclosed subgraphs in flowcharts
    if detected_type in ("flowchart", "graph"):
        subgraph_opens = sum(1 for l in lines if re.match(r"\s*subgraph\b", l))
        subgraph_closes = sum(1 for l in lines if l.strip() == "end")
        if subgraph_opens != subgraph_closes:
            errors.append(
                f"Mismatched subgraph/end blocks: "
                f"{subgraph_opens} subgraph(s) but {subgraph_closes} end(s)"
            )

    for message in _line_warnings(lines, detected_type):
        errors.append(f"Warning: {message}")

    # For requirement diagrams, check basic structure
    if detected_type == "requirementDiagram":
        if "requirement" not in source.lower() and "element" not in source.lower():
            errors.append(
                "requirementDiagram should contain 'requirement' or 'element' definitions"
            )

    # For ER diagrams, check basic structure
    if detected_type == "erDiagram":
        if not re.search(r"\w+\s*\{", source):
            errors.append(
                "erDiagram should contain entity definitions with attributes"
            )

    # Final validity: no errors, or only warnings
    hard_errors = [e for e in errors if not e.startswith("Warning:")]
    is_valid = len(hard_errors) == 0

    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        diagram_type=detected_type,
    )


def clean_mermaid_source(source: str) -> str:
    """
    Clean common issues from Mermaid source returned by LLMs.
    """
    source = source.strip()

    # Remove markdown fences
    source = re.sub(r"^```(?:mermaid)?\s*\n?", "", source)
    source = re.sub(r"\n?```\s*$", "", source)
    source = source.strip()

    # Remove any leading/trailing blank lines
    lines = source.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    return "\n".join(lines)
