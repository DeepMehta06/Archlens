import { useState } from 'react';
import { useQueries, useQuery } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { api } from '@/lib/api';
import { EvidenceQuote } from './EvidenceQuote';
import { ItemDetailSheet } from './ItemDetailSheet';

export function EvidenceTab({ projectId }: { projectId: string }) {
  const [openItemId, setOpenItemId] = useState<string | null>(null);

  const { data: items, isLoading: itemsLoading } = useQuery({
    queryKey: ['ledger', projectId, 'all'],
    queryFn: () => api.listLedger(projectId),
  });

  const detailQueries = useQueries({
    queries: (items ?? []).map((item) => ({
      queryKey: ['ledger-item', item.id],
      queryFn: () => api.getLedgerItem(item.id),
      enabled: Boolean(items),
    })),
  });

  const isLoading = itemsLoading || detailQueries.some((q) => q.isLoading);
  const entries = detailQueries
    .filter((q) => q.data)
    .flatMap((q) => q.data!.evidence.map((ev) => ({ evidence: ev, item: q.data! })));

  const unverifiedFirst = [...entries].sort((a, b) => {
    const rank = { unverified: 0, not_applicable: 1, verified: 2 };
    return rank[a.evidence.verification_status] - rank[b.evidence.verification_status];
  });

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="px-3 pt-3">
        <p className="text-xs text-ink-soft">Every quote the ledger relies on, unverified ones first.</p>
      </div>
      <ScrollArea className="min-h-0 flex-1 overflow-hidden px-3 py-3">
        {isLoading && (
          <div className="flex items-center gap-2 px-1 py-3 text-xs text-ink-soft">
            <Loader2 className="size-3.5 animate-spin" />
            Loading evidence…
          </div>
        )}
        {!isLoading && unverifiedFirst.length === 0 && <p className="px-1 py-3 text-xs text-ink-soft">No evidence recorded yet.</p>}
        <div className="flex flex-col gap-2">
          {unverifiedFirst.map(({ evidence, item }) => (
            <div key={evidence.id}>
              <button onClick={() => setOpenItemId(item.id)} className="mb-1 flex items-center gap-1.5 text-xs text-ink-soft hover:text-brand">
                <span className="font-mono-id rounded bg-canvas-deep px-1.5 py-0.5">{item.display_id}</span>
                {item.title}
              </button>
              <EvidenceQuote evidence={evidence} />
            </div>
          ))}
        </div>
      </ScrollArea>

      <ItemDetailSheet itemId={openItemId} projectId={projectId} open={Boolean(openItemId)} onOpenChange={(open) => !open && setOpenItemId(null)} />
    </div>
  );
}
