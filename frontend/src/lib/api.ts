import type {
  ChangeReport,
  DemoSeedResult,
  Diagram,
  DiagramType,
  HealthStatus,
  ImplementationPrompt,
  Job,
  LedgerItem,
  LedgerItemDetail,
  NotionExportResult,
  Project,
  PromptTarget,
  Question,
  Snapshot,
  Source,
  SourceDetail,
} from './types';

const API_BASE = '/api';

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: init?.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...init,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      // 429 responses use {"error": "..."} instead of the usual {"detail": "..."} shape.
      detail = body.detail ?? body.error ?? detail;
    } catch {
      // response had no JSON body
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthStatus>('/health'),

  createProject: (data: { name: string; description?: string; my_name?: string }) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(data) }),
  listProjects: () => request<Project[]>('/projects'),
  getProject: (id: string) => request<Project>(`/projects/${id}`),

  listSources: (projectId: string) => request<Source[]>(`/projects/${projectId}/sources`),
  getSource: (projectId: string, sourceId: string) => request<SourceDetail>(`/projects/${projectId}/sources/${sourceId}`),
  updateSource: (projectId: string, sourceId: string, data: { me: string }) =>
    request<Source>(`/projects/${projectId}/sources/${sourceId}`, { method: 'PATCH', body: JSON.stringify(data) }),
  addTextSource: (projectId: string, data: { text: string; label?: string; me?: string; analyze?: boolean }) =>
    request<{ source: Source; job: Job }>(`/projects/${projectId}/sources`, {
      method: 'POST',
      body: JSON.stringify({ analyze: true, ...data }),
    }),
  uploadSource: (projectId: string, file: File, options?: { me?: string; analyze?: boolean }) => {
    const form = new FormData();
    form.append('file', file);
    if (options?.me) form.append('me', options.me);
    form.append('analyze', String(options?.analyze ?? true));
    return request<{ source: Source; job: Job }>(`/projects/${projectId}/sources/upload`, { method: 'POST', body: form });
  },

  connectGithubSource: (projectId: string, data: { repo: string; ref?: string; analyze?: boolean }) =>
    request<{ source: Source; job: Job }>(`/projects/${projectId}/sources/github`, {
      method: 'POST',
      body: JSON.stringify({ analyze: true, ...data }),
    }),

  getJob: (id: string) => request<Job>(`/jobs/${id}`),

  listLedger: (projectId: string, params?: { status?: string; type?: string; evidence_status?: string }) => {
    const qs = params ? `?${new URLSearchParams(params as Record<string, string>).toString()}` : '';
    return request<LedgerItem[]>(`/projects/${projectId}/ledger${qs}`);
  },
  getLedgerItem: (id: string) => request<LedgerItemDetail>(`/ledger-items/${id}`),
  updateLedgerItem: (id: string, data: Partial<Pick<LedgerItem, 'title' | 'description' | 'item_type' | 'evidence_status' | 'approval_status' | 'risk_level'>>) =>
    request<LedgerItem>(`/ledger-items/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  generateImplementationPrompt: (itemId: string, target: PromptTarget = 'generic') =>
    request<ImplementationPrompt>(`/ledger-items/${itemId}/prompt`, { method: 'POST', body: JSON.stringify({ target }) }),

  listQuestions: (projectId: string, status = 'open') => request<Question[]>(`/projects/${projectId}/questions?status=${status}`),
  updateQuestion: (id: string, data: { status?: string; resolution_note?: string }) =>
    request<Question>(`/questions/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),

  draftMessage: (projectId: string, data: { language: 'english' | 'hinglish'; question_ids?: string[] }) =>
    request<{ language: string; text: string; question_ids: string[] }>(`/projects/${projectId}/draft-message`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  createSnapshot: (projectId: string, label?: string) =>
    request<Snapshot>(`/projects/${projectId}/snapshots`, { method: 'POST', body: JSON.stringify({ label }) }),
  listSnapshots: (projectId: string) => request<Snapshot[]>(`/projects/${projectId}/snapshots`),

  compare: (projectId: string, data: { snapshot_id: string; incoming_text: string }) =>
    request<ChangeReport>(`/projects/${projectId}/compare`, { method: 'POST', body: JSON.stringify(data) }),
  getChangeReport: (id: string) => request<ChangeReport>(`/change-reports/${id}`),

  createDiagram: (projectId: string, data: { diagram_type: DiagramType; focus?: string }) =>
    request<Diagram>(`/projects/${projectId}/diagrams`, { method: 'POST', body: JSON.stringify(data) }),
  listDiagrams: (projectId: string) => request<Diagram[]>(`/projects/${projectId}/diagrams`),

  exportUrl: (projectId: string) => `${API_BASE}/projects/${projectId}/export.md`,
  exportNotion: (projectId: string) => request<NotionExportResult>(`/projects/${projectId}/export/notion`, { method: 'POST' }),

  chatHistory: (projectId: string, threadId: string) => request(`/projects/${projectId}/chat/messages?thread_id=${threadId}`),

  demoSeed: () => request<DemoSeedResult>('/demo/seed', { method: 'POST' }),
};

export { ApiError };
