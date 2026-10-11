import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Loader2, Printer, X } from 'lucide-react';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { api } from '@/lib/api';
import { evidenceBadge, itemTypeLabel, riskBadge } from '@/lib/badges';
import { EvidenceQuote } from './EvidenceQuote';
import type { ApprovalStatus, EvidenceStatus, ItemType, LedgerItemDetail, RiskLevel } from '@/lib/types';

function ItemDetailContent({ item, projectId }: { item: LedgerItemDetail; projectId: string }) {
  const queryClient = useQueryClient();
  const [description, setDescription] = useState(item.description);

  const update = useMutation({
    mutationFn: (data: Parameters<typeof api.updateLedgerItem>[1]) => api.updateLedgerItem(item.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ledger-item', item.id] });
      queryClient.invalidateQueries({ queryKey: ['ledger', projectId] });
    },
  });

  const setApproval = (approval_status: ApprovalStatus) => update.mutate({ approval_status });

  return (
    <div className="print-area flex h-full flex-col overflow-y-auto">
      <SheetHeader className="border-b border-border/70">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="font-mono-id rounded bg-canvas-deep px-1.5 py-0.5 text-xs text-ink-soft">{item.display_id}</span>
            <span className="text-xs text-ink-soft">{itemTypeLabel(item.item_type)}</span>
          </div>
          <Button size="icon-sm" variant="ghost" onClick={() => window.print()} aria-label="Save as PDF" title="Save as PDF">
            <Printer className="size-3.5" />
          </Button>
        </div>
        <SheetTitle>{item.title}</SheetTitle>
      </SheetHeader>

      <div className="flex flex-col gap-5 p-4">
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant={item.approval_status === 'approved' ? 'default' : 'outline'} onClick={() => setApproval('approved')} disabled={update.isPending}>
            <Check className="size-3.5" />
            Approve
          </Button>
          <Button size="sm" variant={item.approval_status === 'rejected' ? 'destructive' : 'outline'} onClick={() => setApproval('rejected')} disabled={update.isPending}>
            <X className="size-3.5" />
            Reject
          </Button>
          {item.approval_status !== 'needs_review' && (
            <Button size="sm" variant="ghost" onClick={() => setApproval('needs_review')} disabled={update.isPending}>
              Reset to needs review
            </Button>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <p className="mb-1 text-xs font-medium text-ink-soft">Type</p>
            <Select value={item.item_type} onValueChange={(v) => update.mutate({ item_type: v as ItemType })}>
              <SelectTrigger size="sm" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(['requirement', 'constraint', 'decision', 'assumption'] as ItemType[]).map((t) => (
                  <SelectItem key={t} value={t}>
                    {itemTypeLabel(t)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div>
            <p className="mb-1 text-xs font-medium text-ink-soft">Risk</p>
            <Select value={item.risk_level} onValueChange={(v) => update.mutate({ risk_level: v as RiskLevel })}>
              <SelectTrigger size="sm" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(['low', 'medium', 'high'] as RiskLevel[]).map((r) => (
                  <SelectItem key={r} value={r}>
                    {riskBadge(r).label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="col-span-2">
            <p className="mb-1 text-xs font-medium text-ink-soft">Evidence certainty (how firmly the client said it)</p>
            <Select value={item.evidence_status} onValueChange={(v) => update.mutate({ evidence_status: v as EvidenceStatus })}>
              <SelectTrigger size="sm" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(['explicit', 'tentative', 'inferred', 'unknown'] as EvidenceStatus[]).map((e) => (
                  <SelectItem key={e} value={e}>
                    {evidenceBadge(e).label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div>
          <p className="mb-1 text-xs font-medium text-ink-soft">Description</p>
          <Textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onBlur={() => description !== item.description && update.mutate({ description })}
            className="min-h-20 text-sm"
          />
        </div>

        <Separator />

        <div>
          <p className="mb-2 text-sm font-medium text-ink">
            Evidence ({item.evidence_verified}/{item.evidence_total} verified)
          </p>
          <div className="flex flex-col gap-2">
            {item.evidence.map((ev) => (
              <EvidenceQuote key={ev.id} evidence={ev} />
            ))}
          </div>
        </div>

        {item.questions.length > 0 && (
          <>
            <Separator />
            <div>
              <p className="mb-2 text-sm font-medium text-ink">Related questions</p>
              <div className="flex flex-col gap-2">
                {item.questions.map((q) => (
                  <div key={q.id} className="rounded-lg border border-border bg-background/60 p-2.5">
                    <p className="text-sm text-ink">{q.question}</p>
                    <Badge variant={q.status === 'open' ? 'caution' : 'outline'} className="mt-1.5">
                      {q.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function ItemDetailSheet({ itemId, projectId, open, onOpenChange }: { itemId: string | null; projectId: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const { data: item, isLoading } = useQuery({
    queryKey: ['ledger-item', itemId],
    queryFn: () => api.getLedgerItem(itemId!),
    enabled: Boolean(itemId) && open,
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full p-0 sm:max-w-lg">
        {isLoading || !item ? (
          <div className="flex h-full items-center justify-center text-ink-soft">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : (
          <ItemDetailContent key={item.id} item={item} projectId={projectId} />
        )}
      </SheetContent>
    </Sheet>
  );
}
