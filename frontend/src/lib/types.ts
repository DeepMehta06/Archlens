export type ItemType = 'requirement' | 'constraint' | 'decision' | 'assumption';
export type EvidenceStatus = 'explicit' | 'tentative' | 'inferred' | 'unknown';
export type ApprovalStatus = 'needs_review' | 'approved' | 'rejected';
export type RiskLevel = 'low' | 'medium' | 'high';
export type SpeakerRole = 'client' | 'you' | 'unknown';
export type VerificationStatus = 'verified' | 'unverified' | 'not_applicable';
export type EvidenceKind = 'text_quote' | 'transcript_quote' | 'visual_observation';
export type QuestionPriority = 'low' | 'medium' | 'high';
export type QuestionStatus = 'open' | 'resolved' | 'dismissed';
export type SourceStatus = 'uploaded' | 'processing' | 'processed' | 'failed';
export type SourceType = 'text' | 'whatsapp' | 'image' | 'audio' | 'pdf' | 'github_repo';
export type PromptTarget = 'generic' | 'claude_code' | 'cursor' | 'github_copilot';
export type JobStatus = 'queued' | 'processing' | 'completed' | 'failed';
export type ChangeClassification = 'already_covered' | 'new_requirement' | 'contradiction' | 'unclear';
export type DiagramType = 'architecture' | 'sequence' | 'er' | 'component' | 'requirements';

export interface Project {
  id: string;
  name: string;
  description: string | null;
  my_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface Source {
  id: string;
  project_id: string;
  label: string | null;
  status: SourceStatus;
  source_type: SourceType;
  me: string | null;
  created_at: string;
  metadata_json?: { needs_me?: boolean; [key: string]: unknown } | null;
}

export interface ChunkLocation {
  file_path: string;
  start_line: number;
  end_line: number;
}

export interface SourceDetail extends Source {
  chunks: Array<{ id: string; units_json: EvidenceChunkMessage[]; location_json?: ChunkLocation | null }>;
}

export interface Job {
  id: string;
  status: JobStatus;
  stage: string | null;
  progress: number;
  error_message: string | null;
  result_json: Record<string, unknown> | null;
}

export interface LedgerItem {
  id: string;
  project_id: string;
  display_id: string;
  item_type: ItemType;
  title: string;
  description: string;
  evidence_status: EvidenceStatus;
  approval_status: ApprovalStatus;
  risk_level: RiskLevel;
  stated_by: SpeakerRole;
  evidence_total: number;
  evidence_verified: number;
  open_questions: number;
}

export interface EvidenceChunkMessage {
  n: number;
  sender: string;
  text: string;
  timestamp_text: string | null;
}

export interface Evidence {
  id: string;
  quote: string;
  highlight: string;
  unit_numbers: number[];
  speaker: string;
  speaker_role: SpeakerRole;
  verification_status: VerificationStatus;
  verification_note: string | null;
  source_label: string | null;
  evidence_kind: EvidenceKind;
  chunk: {
    id: string;
    units_json: EvidenceChunkMessage[];
  } | null;
}

export interface Question {
  id: string;
  question: string;
  reason: string;
  priority: QuestionPriority;
  status: QuestionStatus;
  ledger_item_id: string | null;
  resolution_note: string | null;
}

export interface LedgerItemDetail extends LedgerItem {
  evidence: Evidence[];
  questions: Question[];
}

export interface ChangeReportResult {
  incoming_claim: string;
  classification: ChangeClassification;
  related_display_ids: string[];
  related_baseline_item_ids: string[];
  supporting_chunk_ids: string[];
  explanation: string;
  confidence: number;
  candidate_item_id: string | null;
}

export interface ChangeReport {
  id: string;
  snapshot_label: string | null;
  results: ChangeReportResult[];
  draft_message: string | null;
}

export interface Snapshot {
  id: string;
  project_id: string;
  version: number;
  label: string | null;
  created_at: string;
  snapshot_json?: { items?: unknown[] } | null;
}

export interface Diagram {
  id: string;
  project_id: string;
  diagram_type: DiagramType;
  title: string;
  mermaid_source: string;
  warnings_json: string[];
  created_at: string;
}

export interface HealthStatus {
  status: string;
  version: string;
  ollama_reachable: boolean;
  model: string;
  model_installed: boolean;
  embed_model: string;
  embed_model_installed: boolean;
  retrieval_mode: 'hybrid' | 'bm25_only';
  fts5: boolean;
  privacy: string;
  error: string | null;
}

export interface ImplementationPrompt {
  prompt: string;
  target: PromptTarget;
  affected_files: ChunkLocation[];
}

export interface NotionExportResult {
  page_id: string;
  url: string;
}

export interface DemoSeedResult {
  project: Project;
  sources: Source[];
  job: Job;
  compare_example: string;
  created: boolean;
}

// --- Chat stream types ---

export type ChatStreamEventType = 'thread' | 'status' | 'token' | 'replace' | 'card' | 'citations' | 'error' | 'done';

export interface ChatCitation {
  marker: string;
  kind: 'chunk' | 'ledger_item';
  chunk_id?: string;
  source_id?: string;
  source_label?: string;
  snippet?: string;
  ledger_item_id?: string;
  display_id?: string;
}

export type ChatCard =
  | { type: 'ledger_list'; items: LedgerItem[] }
  | { type: 'questions'; questions: Question[] }
  | { type: 'draft_message'; language: 'english' | 'hinglish'; text: string; question_ids: string[] }
  | { type: 'diagram'; diagram_id: string; diagram_type: DiagramType; title: string; mermaid_source: string; warnings: string[] }
  | { type: 'change_report'; report_id: string; snapshot_label: string | null; results: ChangeReportResult[] }
  | { type: 'confirm_add_source'; preview: string; char_count: number; looks_like_whatsapp: boolean }
  | { type: 'error'; message: string };

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations: ChatCitation[];
  cards: ChatCard[];
  grounded: boolean | null;
}
