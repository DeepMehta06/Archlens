"""Shared enumerations for the ArchLens domain model and API."""
from enum import Enum


class SourceType(str, Enum):
    TEXT = "text"
    WHATSAPP = "whatsapp"
    IMAGE = "image"
    AUDIO = "audio"
    PDF = "pdf"


class SourceStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ItemType(str, Enum):
    REQUIREMENT = "requirement"
    CONSTRAINT = "constraint"
    DECISION = "decision"
    ASSUMPTION = "assumption"


class EvidenceStatus(str, Enum):
    EXPLICIT = "explicit"
    TENTATIVE = "tentative"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class ApprovalStatus(str, Enum):
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceKind(str, Enum):
    TEXT_QUOTE = "text_quote"
    TRANSCRIPT_QUOTE = "transcript_quote"
    VISUAL_OBSERVATION = "visual_observation"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    NOT_APPLICABLE = "not_applicable"


class StatedBy(str, Enum):
    CLIENT = "client"
    YOU = "you"
    UNKNOWN = "unknown"


class QuestionPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class QuestionStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChangeClass(str, Enum):
    ALREADY_COVERED = "already_covered"
    NEW_REQUIREMENT = "new_requirement"
    CONTRADICTION = "contradiction"
    UNCLEAR = "unclear"


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


ITEM_PREFIXES = {
    ItemType.REQUIREMENT: "REQ",
    ItemType.CONSTRAINT: "CON",
    ItemType.DECISION: "DEC",
    ItemType.ASSUMPTION: "ASM",
}
