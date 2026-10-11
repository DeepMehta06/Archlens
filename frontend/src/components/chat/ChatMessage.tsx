import { AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ChatMessage as ChatMessageType } from '@/lib/types';
import { CardRenderer } from './CardRenderer';

const MARKER_RE = /\[([CL]\d+)\]/g;

/** Render inline text with bold, italic, inline-code, and citation markers */
function renderInline(text: string, citations: ChatMessageType['citations']): React.ReactNode[] {
  // Tokenise: **bold**, *italic*, _italic_, `code`, [CL\d+]
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*|_(.+?)_|`([^`]+)`|\[([CL]\d+)\])/g;
  const nodes: React.ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  re.lastIndex = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    if (m[2] !== undefined) {
      nodes.push(<strong key={m.index}>{m[2]}</strong>);
    } else if (m[3] !== undefined) {
      nodes.push(<em key={m.index}>{m[3]}</em>);
    } else if (m[4] !== undefined) {
      nodes.push(<em key={m.index}>{m[4]}</em>);
    } else if (m[5] !== undefined) {
      nodes.push(
        <code key={m.index} className="rounded bg-ink/10 px-1 py-0.5 font-mono text-[0.8em]">
          {m[5]}
        </code>,
      );
    } else if (m[6] !== undefined) {
      const marker = m[6];
      const citation = citations.find((c) => c.marker === marker);
      nodes.push(
        <span
          key={`${marker}-${m.index}`}
          title={citation?.snippet ?? citation?.source_label ?? citation?.display_id ?? marker}
          className="mx-0.5 inline-flex cursor-default items-center rounded bg-accent-bg px-1 font-mono-id text-[0.7rem] text-accent-foreground"
        >
          {marker}
        </span>,
      );
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

/** Parse markdown text into React nodes — handles headers, bullets, paragraphs */
function renderMarkdown(content: string, citations: ChatMessageType['citations']): React.ReactNode[] {
  const lines = content.split('\n');
  const nodes: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const raw = lines[i];
    const line = raw.trimStart();

    // Blank line — skip (paragraph spacing handled by gap)
    if (line === '') {
      i++;
      continue;
    }

    // H3 ###
    if (line.startsWith('### ')) {
      nodes.push(
        <h3 key={i} className="mt-2 text-sm font-semibold text-ink">
          {renderInline(line.slice(4), citations)}
        </h3>,
      );
      i++;
      continue;
    }

    // H2 ##
    if (line.startsWith('## ')) {
      nodes.push(
        <h2 key={i} className="mt-2 text-sm font-bold text-ink">
          {renderInline(line.slice(3), citations)}
        </h2>,
      );
      i++;
      continue;
    }

    // H1 #
    if (line.startsWith('# ')) {
      nodes.push(
        <h1 key={i} className="mt-2 text-base font-bold text-ink">
          {renderInline(line.slice(2), citations)}
        </h1>,
      );
      i++;
      continue;
    }

    // Bullet: *, -, •
    if (/^[\*\-•]\s/.test(line)) {
      const items: React.ReactNode[] = [];
      while (i < lines.length && /^[\*\-•]\s/.test(lines[i].trimStart())) {
        const itemText = lines[i].trimStart().replace(/^[\*\-•]\s/, '');
        items.push(
          <li key={i} className="ml-1">
            {renderInline(itemText, citations)}
          </li>,
        );
        i++;
      }
      nodes.push(
        <ul key={`ul-${i}`} className="my-1 list-disc space-y-0.5 pl-4">
          {items}
        </ul>,
      );
      continue;
    }

    // Numbered list: 1. 2. etc.
    if (/^\d+\.\s/.test(line)) {
      const items: React.ReactNode[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i].trimStart())) {
        const itemText = lines[i].trimStart().replace(/^\d+\.\s/, '');
        items.push(
          <li key={i} className="ml-1">
            {renderInline(itemText, citations)}
          </li>,
        );
        i++;
      }
      nodes.push(
        <ol key={`ol-${i}`} className="my-1 list-decimal space-y-0.5 pl-4">
          {items}
        </ol>,
      );
      continue;
    }

    // Normal paragraph line
    nodes.push(
      <p key={i} className="leading-relaxed">
        {renderInline(line, citations)}
      </p>,
    );
    i++;
  }

  return nodes;
}

export function ChatMessage({ message, projectId, onSourceAdded }: { message: ChatMessageType; projectId: string; onSourceAdded: (jobId: string) => void }) {
  const isUser = message.role === 'user';

  return (
    <div className={cn('flex w-full', isUser ? 'justify-end' : 'justify-start')}>
      <div className={cn('flex max-w-[85%] flex-col gap-2', isUser && 'items-end')}>
        <div
          className={cn(
            'rounded-2xl px-4 py-2.5 text-sm',
            isUser ? 'bg-ink text-white' : 'glass-panel text-ink',
          )}
        >
          {message.content ? (
            isUser ? (
              // User messages: plain with pre-wrap
              <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
            ) : (
              // Assistant messages: render markdown
              <div className="flex flex-col gap-1">
                {renderMarkdown(message.content, message.citations)}
              </div>
            )
          ) : isUser ? (
            ''
          ) : (
            <span className="text-ink-soft">…</span>
          )}
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
