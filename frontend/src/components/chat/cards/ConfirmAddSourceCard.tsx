import { useState } from 'react';
import { FilePlus2, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';

export function ConfirmAddSourceCard({ projectId, preview, charCount, looksLikeWhatsapp, onAdded }: { projectId: string; preview: string; charCount: number; looksLikeWhatsapp: boolean; onAdded: (jobId: string) => void }) {
  const [status, setStatus] = useState<'idle' | 'adding' | 'added'>('idle');

  const confirm = async () => {
    setStatus('adding');
    try {
      const { job } = await api.addTextSource(projectId, { text: preview, analyze: true });
      setStatus('added');
      onAdded(job.id);
    } catch {
      setStatus('idle');
    }
  };

  return (
    <div className="glass-panel rounded-lg p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-ink">
        <FilePlus2 className="size-4 text-brand" />
        {looksLikeWhatsapp ? 'This looks like a WhatsApp export' : 'Add this as a source'}
      </div>
      <p className="rounded-md bg-background/70 p-2.5 text-xs text-ink-soft">
        {preview.slice(0, 220)}
        {preview.length > 220 ? '…' : ''}
      </p>
      <p className="mt-1.5 text-xs text-muted-foreground">{charCount.toLocaleString()} characters</p>
      <div className="mt-2 flex gap-2">
        <Button size="sm" onClick={confirm} disabled={status !== 'idle'}>
          {status === 'adding' && <Loader2 className="size-3.5 animate-spin" />}
          {status === 'added' ? 'Added, analyzing…' : 'Add and analyze'}
        </Button>
      </div>
    </div>
  );
}
