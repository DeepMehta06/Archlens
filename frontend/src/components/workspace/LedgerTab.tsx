import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import { api } from '@/lib/api';
import { approvalBadge, evidenceBadge, itemTypeLabel } from '@/lib/badges';
import { ItemDetailSheet } from './ItemDetailSheet';
import type { ApprovalStatus, ItemType } from '@/lib/types';

const ALL = 'all';

export function LedgerTab({ projectId }: { projectId: string }) {
  const [statusFilter, setStatusFilter] = useState<ApprovalStatus | typeof ALL>(ALL);
  const [typeFilter, setTypeFilter] = useState<ItemType | typeof ALL>(ALL);
  const [openItemId, setOpenItemId] = useState<string | null>(null);

  const { data: items, isLoading } = useQuery({
    queryKey: ['ledger', projectId, statusFilter, typeFilter],
    queryFn: () =>
      api.listLedger(projectId, {
        ...(statusFilter !== ALL && { status: statusFilter }),
        ...(typeFilter !== ALL && { type: typeFilter }),
      }),
  });

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex gap-2 px-3 pt-3">
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as ApprovalStatus | typeof ALL)}>
          <SelectTrigger size="sm" className="flex-1">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            <SelectItem value="needs_review">Needs review</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="rejected">Rejected</SelectItem>
          </SelectContent>
        </Select>
        <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v as ItemType | typeof ALL)}>
          <SelectTrigger size="sm" className="flex-1">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All types</SelectItem>
            <SelectItem value="requirement">Requirement</SelectItem>
            <SelectItem value="constraint">Constraint</SelectItem>
            <SelectItem value="decision">Decision</SelectItem>
            <SelectItem value="assumption">Assumption</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <ScrollArea className="min-h-0 flex-1 overflow-hidden px-3 py-3">
        {isLoading && (
          <div className="flex items-center gap-2 px-1 py-3 text-xs text-ink-soft">
            <Loader2 className="size-3.5 animate-spin" />
            Loading ledger…
          </div>
        )}
        {!isLoading && items?.length === 0 && <p className="px-1 py-3 text-xs text-ink-soft">No items match these filters.</p>}
        <ul className="flex flex-col gap-2">
          {items?.map((item) => {
            const approval = approvalBadge(item.approval_status);
            const evidence = evidenceBadge(item.evidence_status);
            return (
              <li key={item.id} className="min-w-0 w-full">
                <button
                  onClick={() => setOpenItemId(item.id)}
                  className="block w-full overflow-hidden rounded-lg border border-border bg-background/60 p-2.5 text-left transition-colors hover:border-brand/40"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono-id rounded bg-canvas-deep px-1.5 py-0.5 text-[0.7rem] text-ink-soft">{item.display_id}</span>
                    <span className="text-xs text-ink-soft">{itemTypeLabel(item.item_type)}</span>
                  </div>
                  <p className="mt-1 truncate text-sm font-medium text-ink">{item.title}</p>
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    <Badge variant={approval.variant}>{approval.label}</Badge>
                    <Badge variant={evidence.variant}>{evidence.label}</Badge>
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      </ScrollArea>

      <ItemDetailSheet itemId={openItemId} projectId={projectId} open={Boolean(openItemId)} onOpenChange={(open) => !open && setOpenItemId(null)} />
    </div>
  );
}
