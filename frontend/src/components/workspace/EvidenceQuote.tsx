import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { Evidence } from '@/lib/types';

const VERIFICATION_BADGE = {
  verified: { label: 'Verified', variant: 'verified' as const },
  unverified: { label: 'Unverified', variant: 'danger' as const },
  not_applicable: { label: 'Not applicable', variant: 'outline' as const },
};

function highlightWithin(text: string, highlight: string) {
  if (!highlight) return text;
  const idx = text.indexOf(highlight);
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="rounded bg-caution-soft px-0.5 text-ink">{highlight}</mark>
      {text.slice(idx + highlight.length)}
    </>
  );
}

export function EvidenceQuote({ evidence }: { evidence: Evidence }) {
  const [expanded, setExpanded] = useState(false);
  const badge = VERIFICATION_BADGE[evidence.verification_status];

  return (
    <div className="rounded-lg border border-border bg-background/60 p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-ink">"{evidence.quote}"</p>
        <div className="flex shrink-0 gap-1">
          {evidence.evidence_kind === 'transcript_quote' && <Badge variant="outline">From transcript</Badge>}
          <Badge variant={badge.variant}>{badge.label}</Badge>
        </div>
      </div>
      <p className="mt-1.5 text-xs text-ink-soft">
        {evidence.speaker} ({evidence.speaker_role}) in {evidence.source_label ?? 'source'}
      </p>
      {evidence.verification_note && <p className="mt-1 text-xs text-caution">{evidence.verification_note}</p>}

      {evidence.chunk && evidence.chunk.units_json.length > 0 && (
        <>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="mt-2 flex items-center gap-1 text-xs font-medium text-brand hover:text-accent-deep"
          >
            {expanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
            {expanded ? 'Hide context' : 'Show in context'}
          </button>
          {expanded && (
            <div className="mt-2 flex flex-col gap-1.5 rounded-md bg-canvas-deep p-2.5">
              {evidence.chunk.units_json.map((unit) => {
                const isCited = evidence.unit_numbers.includes(unit.n);
                return (
                  <p key={unit.n} className={cn('text-xs leading-relaxed', isCited ? 'text-ink' : 'text-ink-soft')}>
                    <span className="font-medium">{unit.sender}: </span>
                    {isCited ? highlightWithin(unit.text, evidence.highlight) : unit.text}
                  </p>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
