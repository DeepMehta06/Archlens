import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables: {
    primaryColor: '#ebe8fd',
    primaryBorderColor: '#5847eb',
    primaryTextColor: '#1c1a2b',
    lineColor: '#9b93f0',
    fontFamily: 'Plus Jakarta Sans, sans-serif',
  },
});

export function MermaidDiagram({ source, id, onSvgReady }: { source: string; id: string; onSvgReady?: (svg: string) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    mermaid
      .render(`mermaid-${id}`, source)
      .then(({ svg }) => {
        if (!cancelled && containerRef.current) {
          containerRef.current.innerHTML = svg;
          onSvgReady?.(svg);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not render this diagram.');
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, id]);

  if (error) {
    return <p className="rounded-md bg-danger-soft px-3 py-2 text-xs text-danger">{error}</p>;
  }

  return <div ref={containerRef} className="overflow-x-auto [&_svg]:max-w-full" />;
}
