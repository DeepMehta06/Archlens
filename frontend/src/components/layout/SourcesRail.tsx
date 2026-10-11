import { useRef, useState, type DragEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileText, Image, AudioLines, Loader2, MessageCircle, Paperclip, UploadCloud } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { ACCEPT_ATTR, SUPPORTED_HINT, UPLOAD_TOOLTIP } from '@/lib/uploads';
import { useSourceUpload } from '@/components/sources/useSourceUpload';
import { NeedsMeDialog } from '@/components/sources/NeedsMeDialog';
import type { SourceStatus, SourceType } from '@/lib/types';

const STATUS_BADGE: Record<SourceStatus, { label: string; variant: 'verified' | 'caution' | 'danger' | 'outline' }> = {
  processed: { label: 'Processed', variant: 'verified' },
  processing: { label: 'Processing', variant: 'caution' },
  uploaded: { label: 'Uploaded', variant: 'outline' },
  failed: { label: 'Failed', variant: 'danger' },
};

function sourceIcon(type: SourceType) {
  if (type === 'whatsapp') return MessageCircle;
  if (type === 'image') return Image;
  if (type === 'audio') return AudioLines;
  return FileText;
}

export function SourcesRail({ projectId }: { projectId: string }) {
  const { data: sources, isLoading } = useQuery({
    queryKey: ['sources', projectId],
    queryFn: () => api.listSources(projectId),
    refetchInterval: 4000,
  });

  const { uploadFiles, uploading, needsMeSource, resolveNeedsMe, dismissNeedsMe } = useSourceUpload(projectId);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFiles = (files: FileList | null) => {
    if (files && files.length > 0) uploadFiles(files);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  };

  return (
    <aside
      className={cn('flex h-full w-72 shrink-0 flex-col border-r border-border/70 bg-background/40 transition-colors', dragOver && 'bg-accent-soft/40')}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
    >
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPT_ATTR}
        multiple
        className="hidden"
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = '';
        }}
      />

      <div className="flex items-start justify-between gap-2 px-4 pt-4 pb-2">
        <div>
          <h2 className="text-sm font-semibold text-ink">Sources</h2>
          <p className="mt-0.5 text-xs text-ink-soft">What the ledger is built from</p>
        </div>
        <Button size="icon-sm" variant="ghost" onClick={() => fileInputRef.current?.click()} disabled={uploading} aria-label="Add source" title={UPLOAD_TOOLTIP}>
          {uploading ? <Loader2 className="size-4 animate-spin" /> : <Paperclip className="size-4" />}
        </Button>
      </div>

      <ScrollArea className="flex-1 px-3 pb-4">
        {isLoading && (
          <div className="flex items-center gap-2 px-2 py-3 text-xs text-ink-soft">
            <Loader2 className="size-3.5 animate-spin" />
            Loading sources…
          </div>
        )}
        {!isLoading && (!sources || sources.length === 0) && (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed border-border px-3 py-8 text-center">
            <UploadCloud className="size-4 text-ink-soft" />
            <p className="text-xs text-ink-soft">No sources yet. Paste a conversation into chat, or</p>
            <Button size="sm" variant="outline" onClick={() => fileInputRef.current?.click()}>
              Add source
            </Button>
            <p className="text-[0.65rem] text-ink-soft">{SUPPORTED_HINT}</p>
          </div>
        )}
        <ul className="flex flex-col gap-1.5">
          {sources?.map((source) => {
            const Icon = sourceIcon(source.source_type);
            const badge = STATUS_BADGE[source.status];
            return (
              <li key={source.id} className={cn('rounded-lg border border-border/70 bg-background/60 p-2.5 transition-colors hover:border-brand/40')}>
                <div className="flex items-start gap-2">
                  <Icon className="mt-0.5 size-3.5 shrink-0 text-brand" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-ink">{source.label ?? 'Untitled source'}</p>
                    <Badge variant={badge.variant} className="mt-1">
                      {badge.label}
                    </Badge>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      </ScrollArea>

      <NeedsMeDialog source={needsMeSource} onResolve={resolveNeedsMe} onDismiss={dismissNeedsMe} />
    </aside>
  );
}
