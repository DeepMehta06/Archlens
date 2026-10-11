import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { GitBranch, Loader2, Lock } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ChangeReportCard } from '@/components/chat/cards/ChangeReportCard';
import { api } from '@/lib/api';
import type { ChangeReport } from '@/lib/types';

export function BaselineTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [label, setLabel] = useState('');
  const [compareText, setCompareText] = useState('');
  const [selectedSnapshot, setSelectedSnapshot] = useState<string>('');
  const [report, setReport] = useState<ChangeReport | null>(null);
  const [comparing, setComparing] = useState(false);

  const { data: snapshots, isLoading } = useQuery({
    queryKey: ['snapshots', projectId],
    queryFn: () => api.listSnapshots(projectId),
  });

  const freeze = useMutation({
    mutationFn: () => api.createSnapshot(projectId, label.trim() || undefined),
    onSuccess: () => {
      setLabel('');
      queryClient.invalidateQueries({ queryKey: ['snapshots', projectId] });
    },
  });

  const runCompare = async () => {
    if (!selectedSnapshot || !compareText.trim()) return;
    setComparing(true);
    try {
      const result = await api.compare(projectId, { snapshot_id: selectedSnapshot, incoming_text: compareText.trim() });
      setReport(result);
    } finally {
      setComparing(false);
    }
  };

  return (
    <ScrollArea className="h-full px-3 py-3">
      <div className="flex flex-col gap-4">
        <div className="rounded-lg border border-border bg-background/60 p-3">
          <p className="flex items-center gap-1.5 text-sm font-medium text-ink">
            <Lock className="size-3.5 text-brand" />
            Freeze a snapshot
          </p>
          <p className="mt-1 text-xs text-ink-soft">Only approved items are included. Snapshots can't be edited or deleted once created.</p>
          <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Label (optional)" className="mt-2 text-sm" />
          <Button size="sm" className="mt-2 w-full" onClick={() => freeze.mutate()} disabled={freeze.isPending}>
            {freeze.isPending && <Loader2 className="size-3.5 animate-spin" />}
            Freeze snapshot
          </Button>
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-ink">Snapshots</p>
          {isLoading && (
            <div className="flex items-center gap-2 text-xs text-ink-soft">
              <Loader2 className="size-3.5 animate-spin" />
              Loading…
            </div>
          )}
          {!isLoading && snapshots?.length === 0 && <p className="text-xs text-ink-soft">No snapshots yet.</p>}
          <ul className="flex flex-col gap-1.5">
            {snapshots?.map((s) => (
              <li key={s.id} className="flex items-center gap-2 rounded-lg border border-border bg-background/60 p-2.5">
                <GitBranch className="size-3.5 shrink-0 text-brand" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-ink">{s.label ?? `Version ${s.version}`}</p>
                  <p className="text-xs text-ink-soft">{new Date(s.created_at).toLocaleDateString()}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        {snapshots && snapshots.length > 0 && (
          <div className="rounded-lg border border-border bg-background/60 p-3">
            <p className="text-sm font-medium text-ink">Compare a new request</p>
            <Select value={selectedSnapshot} onValueChange={setSelectedSnapshot}>
              <SelectTrigger size="sm" className="mt-2 w-full">
                <SelectValue placeholder="Against which snapshot?" />
              </SelectTrigger>
              <SelectContent>
                {snapshots.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.label ?? `Version ${s.version}`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Textarea value={compareText} onChange={(e) => setCompareText(e.target.value)} placeholder="Paste the incoming request…" className="mt-2 min-h-20 text-sm" />
            <Button size="sm" className="mt-2 w-full" onClick={runCompare} disabled={comparing || !selectedSnapshot || !compareText.trim()}>
              {comparing && <Loader2 className="size-3.5 animate-spin" />}
              Compare
            </Button>
          </div>
        )}

        {report && <ChangeReportCard snapshotLabel={report.snapshot_label} results={report.results} />}
      </div>
    </ScrollArea>
  );
}
