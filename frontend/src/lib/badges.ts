import type { ApprovalStatus, EvidenceStatus, RiskLevel } from './types';

export function evidenceBadge(status: EvidenceStatus): { label: string; variant: 'verified' | 'caution' | 'outline' } {
  switch (status) {
    case 'explicit':
      return { label: 'Explicit', variant: 'verified' };
    case 'tentative':
      return { label: 'Tentative', variant: 'caution' };
    case 'inferred':
      return { label: 'Inferred', variant: 'caution' };
    case 'unknown':
      return { label: 'Unknown', variant: 'outline' };
  }
}

export function approvalBadge(status: ApprovalStatus): { label: string; variant: 'verified' | 'caution' | 'danger' } {
  switch (status) {
    case 'approved':
      return { label: 'Approved', variant: 'verified' };
    case 'rejected':
      return { label: 'Rejected', variant: 'danger' };
    case 'needs_review':
      return { label: 'Needs review', variant: 'caution' };
  }
}

export function riskBadge(risk: RiskLevel): { label: string; variant: 'verified' | 'caution' | 'danger' } {
  switch (risk) {
    case 'low':
      return { label: 'Low risk', variant: 'verified' };
    case 'medium':
      return { label: 'Medium risk', variant: 'caution' };
    case 'high':
      return { label: 'High risk', variant: 'danger' };
  }
}

export function itemTypeLabel(type: string): string {
  switch (type) {
    case 'requirement':
      return 'Requirement';
    case 'constraint':
      return 'Constraint';
    case 'decision':
      return 'Decision';
    case 'assumption':
      return 'Assumption';
    default:
      return type;
  }
}
