/**
 * API client — all calls go through FastAPI backend.
 * API keys are NEVER sent from the frontend.
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface Project {
  id: string;
  name: string;
  status: string;
  created_at: string;
  updated_at: string;
  raw_requirements?: string;
  structured_model?: StructuredProjectModel | null;
  gap_analysis?: GapAnalysisResult | null;
  architecture?: ArchitectureResult | null;
  _debug_ai_requests?: number;
  _debug_provider?: string;
}

export type RequirementStatus = 'explicit' | 'inferred' | 'assumed' | 'unknown';

export interface FunctionalRequirement {
  id: string;
  category: string;
  description: string;
  status: RequirementStatus;
}

export interface NonFunctionalRequirement {
  id: string;
  category: string;
  description: string;
  status: RequirementStatus;
  current_value?: string | null;
}

export interface Actor {
  id: string;
  name: string;
  description: string;
  type: string;
}

export interface DataEntity {
  id: string;
  name: string;
  description: string;
  attributes: string[];
  status: RequirementStatus;
}

export interface Assumption {
  id: string;
  description: string;
  reason: string;
}

export interface Ambiguity {
  id: string;
  description: string;
  impact: string;
  related_requirement_ids: string[];
}

export interface MissingInformation {
  id: string;
  area: string;
  description: string;
  impact: string;
}

export interface StructuredProjectModel {
  project_name: string;
  summary: string;
  domain: string;
  stakeholders: string[];
  actors: Actor[];
  functional_requirements: FunctionalRequirement[];
  non_functional_requirements: NonFunctionalRequirement[];
  business_rules: string[];
  constraints: string[];
  data_entities: DataEntity[];
  assumptions: Assumption[];
  ambiguities: Ambiguity[];
  missing_information: MissingInformation[];
  open_questions: string[];
}

export type Priority = 'critical' | 'high' | 'medium' | 'low';

export interface EngineeringQuestion {
  id: string;
  category: string;
  question: string;
  priority: Priority;
  why_it_matters: string;
}

export interface RequirementGap {
  id: string;
  description: string;
  priority: Priority;
  why_it_matters: string;
}

export interface GapAnalysisResult {
  gaps: RequirementGap[];
  questions: EngineeringQuestion[];
  coverage_summary: string;
}

export interface ArchitectureDecision {
  id: string;
  decision: string;
  reason: string;
  alternative?: string | null;
  tradeoff?: string | null;
}

export interface ArchitectureComponent {
  id: string;
  name: string;
  responsibility: string;
}

export interface ArchitectureResult {
  summary: string;
  components: ArchitectureComponent[];
  decisions: ArchitectureDecision[];
  technology_stack: Record<string, string>;
  assumptions: string[];
}

export interface Diagram {
  id: string;
  project_id: string;
  diagram_type: string;
  title: string;
  mermaid_source: string;
  is_valid: boolean;
  version: number;
  validation_errors: string[];
  metadata: {
    provider: string;
    model: string;
    generated_at: string;
    repair_attempts: number;
  } | null;
  created_at: string;
  updated_at: string;
}

export interface InputAssessment {
  is_sufficient: boolean;
  word_count: number;
  statement_count: number;
  min_words: number;
  min_statements: number;
  max_words: number;
  keywords_found: string[];
  accepted_keywords: string[];
  issues: string[];
}

export interface ProviderStatus {
  provider: string;
  model: string;
  available: boolean;
  error?: string | null;
}

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: response.statusText }));
    let errMsg = `HTTP ${response.status}`;
    if (error.detail) {
      if (typeof error.detail === 'object' && error.detail.message) {
        errMsg = error.detail.message;
      } else if (typeof error.detail === 'string') {
        errMsg = error.detail;
      }
    } else if (error.error) {
      errMsg = error.error;
    }
    throw new Error(errMsg);
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

export const api = {
  // Health
  health: () => request<{ status: string; version: string }>('/api/v1/health'),

  providerStatus: () =>
    request<{ active_provider: string; providers: ProviderStatus[]; cloud_warning: string }>(
      '/api/v1/providers/status'
    ),

  assessInput: (text: string) =>
    request<InputAssessment>('/api/v1/input/assess', {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),

  // Projects
  createProject: (name: string, rawRequirements: string) =>
    request<Project>('/api/v1/projects', {
      method: 'POST',
      body: JSON.stringify({ name, raw_requirements: rawRequirements }),
    }),

  listProjects: () => request<Project[]>('/api/v1/projects'),

  getProject: (id: string) => request<Project>(`/api/v1/projects/${id}`),

  updateProject: (id: string, data: { raw_requirements?: string; additional_context?: string }) =>
    request<Project>(`/api/v1/projects/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  deleteProject: (id: string) =>
    fetch(`${API_BASE}/api/v1/projects/${id}`, { method: 'DELETE' }),

  // Analysis
  analyzeProject: (id: string, forceRefresh = false) =>
    request<Project>(`/api/v1/projects/${id}/analyze`, {
      method: 'POST',
      body: JSON.stringify({ force_refresh: forceRefresh }),
    }),

  getRequirements: (id: string) =>
    request<StructuredProjectModel>(`/api/v1/projects/${id}/requirements`),

  getGaps: (id: string) =>
    request<GapAnalysisResult>(`/api/v1/projects/${id}/gaps`),

  getQuestions: (id: string, priority?: string) => {
    const url = priority
      ? `/api/v1/projects/${id}/questions?priority=${priority}`
      : `/api/v1/projects/${id}/questions`;
    return request<{ total: number; questions: EngineeringQuestion[]; coverage_summary: string }>(url);
  },

  // Diagrams
  getDiagrams: (id: string) =>
    request<Diagram[]>(`/api/v1/projects/${id}/diagrams`),

  updateDiagramSource: (projectId: string, diagramId: string, mermaidSource: string) =>
    request<Diagram>(`/api/v1/projects/${projectId}/diagrams/${diagramId}`, {
      method: 'PATCH',
      body: JSON.stringify({ mermaid_source: mermaidSource }),
    }),

  repairDiagram: (projectId: string, diagramId: string) =>
    request<Diagram>(`/api/v1/projects/${projectId}/diagrams/${diagramId}/repair`, {
      method: 'POST',
      body: JSON.stringify({}),
    }),
};
