import { FileText } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { approvalBadge, evidenceBadge, itemTypeLabel } from '@/lib/badges';
import type { LedgerItem } from '@/lib/types';

export function LedgerListCard({ items }: { items: LedgerItem[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground">No ledger items yet.</p>;
  }

  return (
    <div className="glass-panel rounded-lg p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-ink">
        <FileText className="size-4 text-brand" />
        Ledger items ({items.length})
      </div>
      <ul className="flex flex-col gap-2">
        {items.map((item) => {
          const approval = approvalBadge(item.approval_status);
          const evidence = evidenceBadge(item.evidence_status);
          return (
            <li key={item.id} className="rounded-md border border-border bg-background/60 p-2.5">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono-id rounded bg-canvas-deep px-1.5 py-0.5 text-[0.7rem] text-ink-soft">{item.display_id}</span>
                    <span className="text-xs text-ink-soft">{itemTypeLabel(item.item_type)}</span>
                  </div>
                  <p className="mt-1 truncate text-sm font-medium text-ink">{item.title}</p>
                </div>
                <div className="flex shrink-0 gap-1">
                  <Badge variant={approval.variant}>{approval.label}</Badge>
                  <Badge variant={evidence.variant}>{evidence.label}</Badge>
                </div>
              </div>
              <p className="mt-1.5 text-xs text-muted-foreground">
                {item.evidence_verified}/{item.evidence_total} quotes verified
                {item.open_questions > 0 && <span className="ml-2 text-caution">{item.open_questions} open question{item.open_questions === 1 ? '' : 's'}</span>}
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
