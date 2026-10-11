import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Maximize2, Workflow } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { MermaidDiagram } from '@/components/chat/MermaidDiagram';
import { DiagramViewer } from '@/components/chat/DiagramViewer';
import { api } from '@/lib/api';
import type { Diagram, DiagramType } from '@/lib/types';

const DIAGRAM_TYPES: { value: DiagramType; label: string }[] = [
  { value: 'architecture', label: 'Architecture' },
  { value: 'sequence', label: 'Sequence' },
  { value: 'er', label: 'Entity relationship' },
  { value: 'component', label: 'Component' },
  { value: 'requirements', label: 'Requirements' },
];

export function DiagramsTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [diagramType, setDiagramType] = useState<DiagramType>('architecture');
  const [focus, setFocus] = useState('');
  const [focusedDiagram, setFocusedDiagram] = useState<Diagram | null>(null);

  const { data: diagrams, isLoading } = useQuery({
    queryKey: ['diagrams', projectId],
    queryFn: () => api.listDiagrams(projectId),
  });

  const generate = useMutation({
    mutationFn: () => api.createDiagram(projectId, { diagram_type: diagramType, focus: focus.trim() || undefined }),
    onSuccess: () => {
      setFocus('');
      queryClient.invalidateQueries({ queryKey: ['diagrams', projectId] });
    },
  });

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-col gap-2 border-b border-border/70 p-3">
        <Select value={diagramType} onValueChange={(v) => setDiagramType(v as DiagramType)}>
          <SelectTrigger size="sm" className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DIAGRAM_TYPES.map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input value={focus} onChange={(e) => setFocus(e.target.value)} placeholder="Focus area (optional)" className="text-sm" />
        <Button size="sm" onClick={() => generate.mutate()} disabled={generate.isPending}>
          {generate.isPending && <Loader2 className="size-3.5 animate-spin" />}
          Generate diagram
        </Button>
      </div>

      <ScrollArea className="flex-1 px-3 py-3">
        {isLoading && (
          <div className="flex items-center gap-2 px-1 py-3 text-xs text-ink-soft">
            <Loader2 className="size-3.5 animate-spin" />
            Loading diagrams…
          </div>
        )}
        {!isLoading && diagrams?.length === 0 && <p className="px-1 py-3 text-xs text-ink-soft">No diagrams yet. Generate one above, or ask chat.</p>}
        <div className="flex flex-col gap-3">
          {diagrams?.map((d) => (
            <div key={d.id} className="rounded-lg border border-border bg-background/60 p-3">
              <p className="flex items-center gap-1.5 text-sm font-medium text-ink">
                <Workflow className="size-3.5 text-brand" />
                {d.title}
              </p>
              <button
                onClick={() => setFocusedDiagram(d)}
                className="group relative mt-2 w-full rounded-md bg-background/70 p-2 text-left transition-colors hover:bg-background"
                aria-label={`Open ${d.title} full size`}
              >
                <MermaidDiagram source={d.mermaid_source} id={d.id} />
                <span className="absolute top-2 right-2 flex size-6 items-center justify-center rounded-md bg-background/90 text-ink-soft opacity-0 shadow-sm transition-opacity group-hover:opacity-100">
                  <Maximize2 className="size-3.5" />
                </span>
              </button>
              {d.warnings_json.length > 0 && (
                <ul className="mt-2 flex flex-col gap-1">
                  {d.warnings_json.map((w, i) => (
                    <li key={i} className="rounded-md bg-caution-soft px-2 py-1 text-xs text-caution">
                      {w}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>

      {focusedDiagram && (
        <DiagramViewer
          open={Boolean(focusedDiagram)}
          onOpenChange={(open) => !open && setFocusedDiagram(null)}
          title={focusedDiagram.title}
          mermaidSource={focusedDiagram.mermaid_source}
          diagramId={focusedDiagram.id}
        />
      )}
    </div>
  );
}
