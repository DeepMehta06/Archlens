import { useRef, useState } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { Check, Copy, Loader2, Terminal } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { api, ApiError } from '@/lib/api';
import type { ImplementationPrompt, PromptTarget } from '@/lib/types';

const TARGETS: { value: PromptTarget; label: string }[] = [
  { value: 'generic', label: 'Generic' },
  { value: 'claude_code', label: 'Claude Code' },
  { value: 'cursor', label: 'Cursor' },
  { value: 'github_copilot', label: 'GitHub Copilot' },
];

export function ImplementationPromptDialog({ itemId, open, onOpenChange }: { itemId: string; open: boolean; onOpenChange: (open: boolean) => void }) {
  const [target, setTarget] = useState<PromptTarget>('generic');
  const [result, setResult] = useState<ImplementationPrompt | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const outputRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (!result || !outputRef.current) return;
      gsap.from(outputRef.current, { y: 8, opacity: 0, duration: 0.3, ease: 'power2.out' });
    },
    { scope: outputRef, dependencies: [result] },
  );

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const prompt = await api.generateImplementationPrompt(itemId, target);
      setResult(prompt);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError('Connect a GitHub repo as a source first — the brief needs code to cite.');
      } else {
        setError(err instanceof ApiError ? err.message : 'Could not generate a brief.');
      }
    } finally {
      setGenerating(false);
    }
  };

  const copy = async () => {
    if (!result) return;
    await navigator.clipboard.writeText(result.prompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) {
          setResult(null);
          setError(null);
        }
      }}
    >
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Terminal className="size-4 text-brand" />
            Implementation brief
          </DialogTitle>
          <DialogDescription>A grounded prompt for your own coding agent, citing real files from the connected repo.</DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2">
          <Select value={target} onValueChange={(v) => setTarget(v as PromptTarget)}>
            <SelectTrigger size="sm" className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TARGETS.map((t) => (
                <SelectItem key={t.value} value={t.value}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button size="sm" onClick={generate} disabled={generating}>
            {generating && <Loader2 className="size-3.5 animate-spin" />}
            {result ? 'Regenerate' : 'Generate'}
          </Button>
        </div>

        {error && <p className="rounded-md bg-danger-soft px-3 py-2 text-xs text-danger">{error}</p>}

        {result && (
          <div ref={outputRef} className="flex flex-col gap-2">
            <div className="max-h-72 overflow-auto rounded-lg border border-border bg-canvas-deep/60 p-3">
              <pre className="font-mono-id whitespace-pre-wrap text-xs leading-relaxed text-ink">{result.prompt}</pre>
            </div>
            {result.affected_files.length > 0 && (
              <div className="flex flex-col gap-1">
                <p className="text-xs font-medium text-ink-soft">Affected files</p>
                <ul className="flex flex-col gap-1">
                  {result.affected_files.map((f, i) => (
                    <li key={i} className="font-mono-id rounded bg-canvas-deep px-2 py-1 text-[0.7rem] text-ink-soft">
                      {f.file_path}:{f.start_line}-{f.end_line}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          {result && (
            <Button onClick={copy}>
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              {copied ? 'Copied' : 'Copy prompt'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
