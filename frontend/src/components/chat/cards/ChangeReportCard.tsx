import { GitCompare } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { ChangeReportResult } from '@/lib/types';

const classificationBadge = {
  already_covered: { label: 'Already covered', variant: 'verified' as const },
  new_requirement: { label: 'New requirement', variant: 'default' as const },
  contradiction: { label: 'Contradiction', variant: 'danger' as const },
  unclear: { label: 'Unclear', variant: 'caution' as const },
};

export function ChangeReportCard({ snapshotLabel, results }: { snapshotLabel: string | null; results: ChangeReportResult[] }) {
  return (
    <div className="glass-panel rounded-lg p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-ink">
        <GitCompare className="size-4 text-brand" />
        Change report{snapshotLabel ? ` against ${snapshotLabel}` : ''}
      </div>
      <ul className="flex flex-col gap-2">
        {results.map((r, i) => {
          const badge = classificationBadge[r.classification];
          return (
            <li key={i} className="rounded-md border border-border bg-background/60 p-2.5">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-ink">{r.incoming_claim}</p>
                <Badge variant={badge.variant}>{badge.label}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{r.explanation}</p>
              {r.related_display_ids.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {r.related_display_ids.map((id) => (
                    <span key={id} className="font-mono-id rounded bg-canvas-deep px-1.5 py-0.5 text-[0.7rem] text-ink-soft">
                      {id}
                    </span>
                  ))}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
