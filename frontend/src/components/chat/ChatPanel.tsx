import { useEffect, useRef, useState, type DragEvent } from 'react';
import { Loader2, Sparkles, UploadCloud } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useChat } from './use-chat';
import { ChatMessage } from './ChatMessage';
import { ChatComposer } from './ChatComposer';
import { useSourceUpload } from '@/components/sources/useSourceUpload';
import { NeedsMeDialog } from '@/components/sources/NeedsMeDialog';
import { cn } from '@/lib/utils';

const STAGE_LABEL: Record<string, string> = {
  routing: 'Reading your message',
  searching: 'Searching the evidence',
  reformulating: 'Refining the search',
  writing: 'Writing a reply',
  drafting: 'Drafting the message',
  drawing: 'Drawing the diagram',
  comparing: 'Comparing against the baseline',
};

export function ChatPanel({ projectId, onSourceAdded }: { projectId: string; onSourceAdded: (jobId: string) => void }) {
  const { messages, stage, isStreaming, sendMessage } = useChat(projectId);
  const bottomRef = useRef<HTMLDivElement>(null);
  const { uploadFiles, needsMeSource, resolveNeedsMe, dismissNeedsMe } = useSourceUpload(projectId);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, stage]);

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length > 0) uploadFiles(e.dataTransfer.files);
  };

  return (
    <div
      className={cn('relative flex h-full min-w-0 flex-1 flex-col transition-colors', dragOver && 'bg-accent-soft/30')}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
    >
      {dragOver && (
        <div className="pointer-events-none absolute inset-4 z-10 flex flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-accent bg-background/80 text-accent">
          <UploadCloud className="size-6" />
          <p className="text-sm font-medium">Drop to add as a source</p>
        </div>
      )}

      <ScrollArea className="flex-1 px-4 py-4 md:px-6">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 py-16 text-center">
            <div className="glass-panel flex size-12 items-center justify-center rounded-full">
              <Sparkles className="size-5 text-brand" />
            </div>
            <p className="max-w-xs text-sm text-ink-soft">
              Paste a client conversation, drop a chat export, screenshot, PDF or voice note to start building the scope ledger, or ask what's already been
              captured.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {messages.map((m) => (
              <ChatMessage key={m.id} message={m} projectId={projectId} onSourceAdded={onSourceAdded} />
            ))}
            {isStreaming && stage && (
              <div className="flex items-center gap-2 text-xs text-ink-soft">
                <Loader2 className="size-3.5 animate-spin" />
                {STAGE_LABEL[stage] ?? stage}
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        )}
      </ScrollArea>
      <div className="px-4 pb-4 md:px-6">
        <ChatComposer onSend={sendMessage} onAttach={uploadFiles} disabled={isStreaming} />
      </div>

      <NeedsMeDialog source={needsMeSource} onResolve={resolveNeedsMe} onDismiss={dismissNeedsMe} />
    </div>
  );
}
