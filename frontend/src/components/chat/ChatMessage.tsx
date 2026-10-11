import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatMessage as ChatMessageType } from '@/lib/types';
import { CardRenderer } from './CardRenderer';

const MARKER_RE = /\[([CL]\d+)\]/g;

function renderWithCitations(content: string, citations: ChatMessageType['citations']) {
  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  MARKER_RE.lastIndex = 0;
  while ((match = MARKER_RE.exec(content)) !== null) {
    if (match.index > lastIndex) parts.push(content.slice(lastIndex, match.index));
    const marker = match[1];
    const citation = citations.find((c) => c.marker === marker);
    parts.push(
      <span
        key={`${marker}-${match.index}`}
        title={citation?.snippet ?? citation?.source_label ?? citation?.display_id ?? marker}
        className="mx-0.5 inline-flex cursor-default items-center rounded bg-accent-bg px-1 font-mono-id text-[0.7rem] text-accent-foreground"
      >
        {marker}
      </span>,
    );
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < content.length) parts.push(content.slice(lastIndex));
  return parts;
}

export function ChatMessage({ message, projectId, onSourceAdded }: { message: ChatMessageType; projectId: string; onSourceAdded: (jobId: string) => void }) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div className={cn('flex max-w-[85%] flex-col gap-2', isUser && 'items-end')}>
        <div
          className={cn(
            'rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap',
            isUser ? 'bg-ink text-white' : 'glass-panel text-ink',
          )}
        >
          {message.content ? renderWithCitations(message.content, message.citations) : isUser ? '' : <span className="text-ink-soft">…</span>}
        </div>

        {!isUser && message.grounded === false && (
          <div className="flex items-center gap-1.5 text-xs text-caution">
            <AlertCircle className="size-3.5" />
            Not backed by a source
          </div>
        )}

        {message.cards.map((card, i) => (
          <div key={i} className="w-full">
            <CardRenderer card={card} projectId={projectId} onSourceAdded={onSourceAdded} />
          </div>
        ))}
      </div>
    </div>
  );
}
