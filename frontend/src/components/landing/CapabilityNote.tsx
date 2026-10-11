import { useQuery } from '@tanstack/react-query';
import { Cpu } from 'lucide-react';
import { api } from '@/lib/api';

export function CapabilityNote() {
  const { data: health } = useQuery({ queryKey: ['health'], queryFn: api.health, staleTime: 30_000 });

  return (
    <section className="mx-auto max-w-6xl px-6 pb-20">
      <div className="flex flex-col gap-3 rounded-xl border border-border bg-canvas-deep/40 p-6 sm:flex-row sm:items-center sm:gap-5">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-full bg-accent-bg">
          <Cpu className="size-5 text-brand" />
        </div>
        <div>
          <p className="text-sm font-medium text-ink">Runs on a local model, not a cloud AI provider</p>
          <p className="mt-1 text-sm leading-relaxed text-ink-soft">
            Extraction and chat run through Ollama on this machine{health?.model ? ` (${health.model})` : ''}. We haven't
            formally measured extraction accuracy yet, so we won't quote a number for it — the ledger is reviewed by you
            before anything is approved.
          </p>
        </div>
      </div>
    </section>
  );
}
