import { useState } from 'react';
import { Maximize2, Workflow } from 'lucide-react';
import { MermaidDiagram } from '@/components/chat/MermaidDiagram';
import { DiagramViewer } from '@/components/chat/DiagramViewer';

export function DiagramCard({ diagramId, title, mermaidSource, warnings }: { diagramId: string; title: string; mermaidSource: string; warnings: string[] }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="glass-panel rounded-lg p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-ink">
        <Workflow className="size-4 text-brand" />
        {title}
      </div>
      <button
        onClick={() => setOpen(true)}
        className="group relative w-full rounded-md bg-background/70 p-3 text-left transition-colors hover:bg-background"
        aria-label={`Open ${title} full size`}
      >
        <MermaidDiagram source={mermaidSource} id={diagramId} />
        <span className="absolute top-2 right-2 flex size-6 items-center justify-center rounded-md bg-background/90 text-ink-soft opacity-0 shadow-sm transition-opacity group-hover:opacity-100">
          <Maximize2 className="size-3.5" />
        </span>
      </button>
      {warnings.length > 0 && (
        <ul className="mt-2 flex flex-col gap-1">
          {warnings.map((w, i) => (
            <li key={i} className="rounded-md bg-caution-soft px-2.5 py-1.5 text-xs text-caution">
              {w}
            </li>
          ))}
        </ul>
      )}

      <DiagramViewer open={open} onOpenChange={setOpen} title={title} mermaidSource={mermaidSource} diagramId={diagramId} />
    </div>
  );
}
