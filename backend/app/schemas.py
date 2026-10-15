"""Pydantic schemas: model output contracts (validated, never trusted) and API payloads."""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.diagram_specs import (
    ArchitectureDiagramSpec,
    ComponentDiagramSpec,
    ERDiagramSpec,
    RequirementTraceabilitySpec,
    SequenceDiagramSpec,
)
from app.enums import (
    ApprovalStatus,
    ChangeClass,
    EvidenceKind,
    EvidenceStatus,
    ItemType,
    JobStatus,
    QuestionPriority,
    QuestionStatus,
    RiskLevel,
    SourceStatus,
    SourceType,
    StatedBy,
    VerificationStatus,
)

__all__ = [
    "ArchitectureDiagramSpec",
    "ComponentDiagramSpec",
    "ERDiagramSpec",
    "RequirementTraceabilitySpec",
    "SequenceDiagramSpec",
]

# ---------------------------------------------------------------------------
# Model output contracts
# ---------------------------------------------------------------------------


class LlmEvidence(BaseModel):
    chunk_id: str
    units: list[int] = Field(min_length=1)
    phrase: Optional[str] = None


class LlmItem(BaseModel):
    item_type: Literal["requirement", "constraint", "decision", "assumption"]
    title: str
    description: str
    evidence_status: Literal["explicit", "tentative", "inferred", "unknown"]
    risk_level: Literal["low", "medium", "high"]
    evidence: list[LlmEvidence] = Field(min_length=1)


class LlmQuestion(BaseModel):
    item_index: Optional[int] = None
    question: str
    reason: str
    priority: Literal["low", "medium", "high"]


class ExtractionOutput(BaseModel):
    items: list[LlmItem] = Field(default_factory=list)
    questions: list[LlmQuestion] = Field(default_factory=list)


class LlmChange(BaseModel):
    incoming_claim: str
    classification: Literal["already_covered", "new_requirement", "contradiction", "unclear"]
    related_baseline_ids: list[str] = Field(default_factory=list)
    units: list[int] = Field(default_factory=list)
    explanation: str
    confidence: Literal["low", "medium", "high"]


class ChangeOutput(BaseModel):
    changes: list[LlmChange] = Field(default_factory=list)


class RouterOutput(BaseModel):
    intent: Literal[
        "answer_question",
        "list_ledger",
        "draft_message",
        "create_diagram",
        "compare_request",
        "open_questions",
        "general_reasoning",
        "off_topic",
    ]
    query: Optional[str] = None
    diagram_type: Optional[Literal["architecture", "sequence", "er", "component", "requirements"]] = None
    language: Optional[Literal["english", "hinglish"]] = None


class ReformulateOutput(BaseModel):
    give_up: bool
    query: Optional[str] = None


# ---------------------------------------------------------------------------
# API payloads
# ---------------------------------------------------------------------------


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    my_name: Optional[str] = Field(default=None, max_length=120)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    my_name: Optional[str] = Field(default=None, max_length=120)


class SourceUpdate(BaseModel):
    me: str = Field(min_length=1, max_length=120)


class DiagramCreate(BaseModel):
    diagram_type: Literal["architecture", "sequence", "er", "component", "requirements"] = "architecture"
    focus: Optional[str] = None


class DiagramOut(ApiModel):
    id: str
    project_id: str
    diagram_type: str
    title: str
    mermaid_source: str
    warnings_json: Optional[list[str]]
    created_at: datetime


class ProjectOut(ApiModel):
    id: str
    name: str
    description: Optional[str]
    my_name: Optional[str]
    is_demo: bool
    created_at: datetime
    updated_at: datetime


class SourceTextCreate(BaseModel):
    text: str = Field(min_length=1)
    label: Optional[str] = Field(default=None, max_length=200)
    me: Optional[str] = Field(default=None, max_length=120)
    analyze: bool = True


class SourceOut(ApiModel):
    id: str
    project_id: str
    source_type: SourceType
    label: str
    filename: Optional[str]
    mime_type: Optional[str]
    status: SourceStatus
    error_message: Optional[str]
    metadata_json: Optional[dict[str, Any]]
    created_at: datetime
    processed_at: Optional[datetime]


class JobOut(ApiModel):
    id: str
    project_id: str
    source_id: Optional[str]
    job_type: str
    status: JobStatus
    stage: str
    progress: int
    error_message: Optional[str]
    result_json: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: datetime


class SourceCreated(BaseModel):
    source: SourceOut
    job: Optional[JobOut]


class ChunkOut(ApiModel):
    id: str
    source_id: str
    ordinal: int
    text: str
    units_json: list[dict[str, Any]]
    sender: Optional[str]
    timestamp_text: Optional[str]
    location_json: Optional[dict[str, Any]] = None


class EvidenceOut(ApiModel):
    id: str
    source_id: str
    chunk_id: Optional[str]
    evidence_kind: EvidenceKind
    quote: Optional[str]
    highlight: Optional[str]
    unit_numbers: Optional[list[int]]
    speaker: Optional[str]
    speaker_role: StatedBy
    verification_status: VerificationStatus
    verification_note: Optional[str]


class LedgerItemOut(ApiModel):
    id: str
    display_id: str
    item_type: ItemType
    title: str
    description: str
    evidence_status: EvidenceStatus
    approval_status: ApprovalStatus
    risk_level: RiskLevel
    stated_by: StatedBy
    active: bool
    evidence_total: int = 0
    evidence_verified: int = 0
    open_questions: int = 0
    created_at: datetime
    updated_at: datetime


class EvidenceDetail(EvidenceOut):
    source_label: Optional[str] = None
    chunk: Optional[ChunkOut] = None


class LedgerItemDetail(LedgerItemOut):
    evidence: list[EvidenceDetail] = Field(default_factory=list)
    questions: list["QuestionOut"] = Field(default_factory=list)


class LedgerItemPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = Field(default=None, min_length=1)
    item_type: Optional[ItemType] = None
    evidence_status: Optional[EvidenceStatus] = None
    approval_status: Optional[ApprovalStatus] = None
    risk_level: Optional[RiskLevel] = None


class QuestionOut(ApiModel):
    id: str
    project_id: str
    ledger_item_id: Optional[str]
    question: str
    reason: str
    priority: QuestionPriority
    status: QuestionStatus
    resolution_note: Optional[str]
    created_at: datetime


class QuestionPatch(BaseModel):
    status: Optional[QuestionStatus] = None
    resolution_note: Optional[str] = None


class DraftRequest(BaseModel):
    language: Literal["english", "hinglish"] = "english"
    question_ids: Optional[list[str]] = None


class DraftOut(BaseModel):
    language: str
    text: str
    question_ids: list[str]


class SnapshotCreate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=200)


class SnapshotOut(ApiModel):
    id: str
    project_id: str
    version: int
    label: str
    snapshot_json: dict[str, Any]
    created_at: datetime


class CompareRequest(BaseModel):
    snapshot_id: str
    incoming_text: str = Field(min_length=1)


class ChangeResult(BaseModel):
    incoming_claim: str
    classification: ChangeClass
    related_baseline_item_ids: list[str]
    related_display_ids: list[str]
    supporting_chunk_ids: list[str]
    explanation: str
    confidence: str
    candidate_item_id: Optional[str] = None


class ChangeReportOut(ApiModel):
    id: str
    project_id: str
    source_id: Optional[str]
    snapshot_id: str
    results: list[ChangeResult]
    draft_message: Optional[str]
    created_at: datetime


class HealthOut(BaseModel):
    status: str
    version: str
    ollama_reachable: bool
    model: str
    model_installed: bool
    embed_model: str
    embed_model_installed: bool
    retrieval_mode: Literal["hybrid", "bm25_only"]
    fts5: bool
    privacy: str
    error: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    thread_id: Optional[str] = None


class ChatMessageOut(ApiModel):
    id: str
    thread_id: str
    role: str
    content: str
    citations_json: Optional[list[dict[str, Any]]]
    cards_json: Optional[list[dict[str, Any]]]
    created_at: datetime


class NotionExportOut(BaseModel):
    page_id: str
    url: str


class GitHubSourceCreate(BaseModel):
    repo: str = Field(min_length=1)
    ref: Optional[str] = None
    analyze: bool = True


class ChangePromptRequest(BaseModel):
    target: Literal["generic", "claude_code", "cursor", "github_copilot"] = "generic"


class ChangePromptOut(BaseModel):
    prompt: str
    target: str
    affected_files: list[dict[str, Any]]


LedgerItemDetail.model_rebuild()
