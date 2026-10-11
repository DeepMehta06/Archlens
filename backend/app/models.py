"""SQLAlchemy models for the ArchLens scope ledger.

Foreign keys cascade at the database level (SQLite foreign_keys pragma is enabled per
connection). FTS5 index rows are maintained by the lexical search service, not by triggers.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.enums import (
    ApprovalStatus,
    ChatRole,
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


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: Optional[datetime], dialect) -> Optional[datetime]:
        return None if value is None else value.replace(tzinfo=timezone.utc)


def enum_column(enum_cls, **kwargs):
    return mapped_column(
        SAEnum(
            enum_cls,
            native_enum=False,
            length=32,
            validate_strings=True,
            values_callable=lambda e: [m.value for m in e],
        ),
        **kwargs,
    )


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("prj"))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    my_name: Mapped[Optional[str]] = mapped_column(String(120))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("src"))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_type: Mapped[SourceType] = enum_column(SourceType, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    filename: Mapped[Optional[str]] = mapped_column(String(255))
    mime_type: Mapped[Optional[str]] = mapped_column(String(120))
    file_path: Mapped[Optional[str]] = mapped_column(Text)
    raw_text: Mapped[Optional[str]] = mapped_column(Text)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    status: Mapped[SourceStatus] = enum_column(SourceStatus, default=SourceStatus.UPLOADED)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    processed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    __table_args__ = (UniqueConstraint("source_id", "ordinal"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("chk"))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    units_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    char_start: Mapped[Optional[int]] = mapped_column(Integer)
    char_end: Mapped[Optional[int]] = mapped_column(Integer)
    page_number: Mapped[Optional[int]] = mapped_column(Integer)
    message_index: Mapped[Optional[int]] = mapped_column(Integer)
    sender: Mapped[Optional[str]] = mapped_column(String(120))
    timestamp_text: Mapped[Optional[str]] = mapped_column(String(64))
    message_timestamp: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    start_seconds: Mapped[Optional[float]] = mapped_column()
    end_seconds: Mapped[Optional[float]] = mapped_column()
    location_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    embedding_json: Mapped[Optional[list[float]]] = mapped_column(JSON)


class LedgerItem(Base):
    __tablename__ = "ledger_items"
    __table_args__ = (UniqueConstraint("project_id", "display_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("itm"))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    display_id: Mapped[str] = mapped_column(String(16), nullable=False)
    item_type: Mapped[ItemType] = enum_column(ItemType, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_status: Mapped[EvidenceStatus] = enum_column(EvidenceStatus, nullable=False)
    approval_status: Mapped[ApprovalStatus] = enum_column(
        ApprovalStatus, default=ApprovalStatus.NEEDS_REVIEW
    )
    risk_level: Mapped[RiskLevel] = enum_column(RiskLevel, default=RiskLevel.LOW)
    stated_by: Mapped[StatedBy] = enum_column(StatedBy, default=StatedBy.UNKNOWN)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    supersedes_item_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("ledger_items.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)

    evidence_links: Mapped[list["EvidenceLink"]] = relationship(
        back_populates="item", lazy="selectin", passive_deletes=True, order_by="EvidenceLink.created_at"
    )


class EvidenceLink(Base):
    __tablename__ = "evidence_links"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("evd"))
    ledger_item_id: Mapped[str] = mapped_column(
        ForeignKey("ledger_items.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    chunk_id: Mapped[Optional[str]] = mapped_column(ForeignKey("source_chunks.id", ondelete="CASCADE"))
    evidence_kind: Mapped[EvidenceKind] = enum_column(EvidenceKind, nullable=False)
    quote: Mapped[Optional[str]] = mapped_column(Text)
    highlight: Mapped[Optional[str]] = mapped_column(Text)
    unit_numbers: Mapped[Optional[list[int]]] = mapped_column(JSON)
    speaker: Mapped[Optional[str]] = mapped_column(String(120))
    speaker_role: Mapped[StatedBy] = enum_column(StatedBy, default=StatedBy.UNKNOWN)
    verification_status: Mapped[VerificationStatus] = enum_column(
        VerificationStatus, nullable=False
    )
    verification_note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    item: Mapped[LedgerItem] = relationship(back_populates="evidence_links")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("qst"))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ledger_item_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("ledger_items.id", ondelete="SET NULL")
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[QuestionPriority] = enum_column(QuestionPriority, default=QuestionPriority.MEDIUM)
    status: Mapped[QuestionStatus] = enum_column(QuestionStatus, default=QuestionStatus.OPEN)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class ScopeSnapshot(Base):
    __tablename__ = "scope_snapshots"
    __table_args__ = (UniqueConstraint("project_id", "version"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("snp"))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ChangeReport(Base):
    __tablename__ = "change_reports"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("chg"))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("scope_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    results_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    draft_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("job"))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    job_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[JobStatus] = enum_column(JobStatus, default=JobStatus.QUEUED)
    stage: Mapped[str] = mapped_column(String(60), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    result_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)


class Diagram(Base):
    __tablename__ = "diagrams"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("dgm"))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    diagram_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    mermaid_source: Mapped[str] = mapped_column(Text, nullable=False)
    spec_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    warnings_json: Mapped[Optional[list[str]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("thr"))
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), default="Project chat")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: new_id("msg"))
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"), index=True, nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[ChatRole] = enum_column(ChatRole, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations_json: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON)
    cards_json: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
