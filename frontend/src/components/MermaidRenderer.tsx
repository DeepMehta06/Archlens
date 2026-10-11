/**
 * MermaidRenderer — renders Mermaid diagrams in the browser.
 * Uses the modern Mermaid API (v10+) with unique element IDs.
 */
import { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

// Initialize once with ArchLens theme
mermaid.initialize({
  startOnLoad: false,
  theme: 'default',
  themeVariables: {
    primaryColor: '#3b82f6',
    primaryTextColor: '#1e293b',
    primaryBorderColor: '#2563eb',
    lineColor: '#64748b',
    secondaryColor: '#f1f5f9',
    tertiaryColor: '#e2e8f0',
    fontFamily: 'Inter, sans-serif',
    fontSize: '14px',
  },
  flowchart: { curve: 'basis', padding: 20 },
  sequence: { actorMargin: 50, noteMargin: 10 },
  er: { useMaxWidth: true },
  securityLevel: 'loose',
});

let diagramCounter = 0;

interface MermaidRendererProps {
  source: string;
  onError?: (error: string) => void;
}

export function MermaidRenderer({ source, onError }: MermaidRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [isRendering, setIsRendering] = useState(false);
  const idRef = useRef(`mermaid-${++diagramCounter}`);

  useEffect(() => {
    if (!source || !containerRef.current) return;

    let cancelled = false;

    const render = async () => {
      setIsRendering(true);
      setRenderError(null);

      try {
        // Parse first to detect errors early
        await mermaid.parse(source);

        if (cancelled) return;

        const { svg } = await mermaid.render(idRef.current, source);

        if (cancelled) return;

        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
          // Make SVG responsive
          const svgEl = containerRef.current.querySelector('svg');
          if (svgEl) {
            svgEl.style.maxWidth = '100%';
            svgEl.style.height = 'auto';
            svgEl.removeAttribute('height');
          }
        }
      } catch (err: unknown) {
        if (cancelled) return;
        const errorMsg = err instanceof Error ? err.message : String(err);
        setRenderError(errorMsg);
        onError?.(errorMsg);
        if (containerRef.current) {
          containerRef.current.innerHTML = '';
        }
        // Increment counter to avoid ID conflicts on retry
        idRef.current = `mermaid-${++diagramCounter}`;
      } finally {
        if (!cancelled) setIsRendering(false);
      }
    };

    // Small debounce for editor changes
    const timer = setTimeout(render, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [source]);

  return (
    <div style={{ width: '100%', minHeight: '100px', position: 'relative' }}>
      {isRendering && (
        <div style={{
          position: 'absolute', top: '50%', left: '50%',
          transform: 'translate(-50%, -50%)',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem',
        }}>
          <div className="loading-spinner" />
          <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Rendering…</span>
        </div>
      )}
      {renderError && (
        <div style={{
          padding: '1rem',
          background: 'rgba(244, 63, 94, 0.08)',
          border: '1px solid rgba(244, 63, 94, 0.3)',
          borderRadius: '8px',
          color: '#f43f5e',
          fontSize: '0.8rem',
          fontFamily: 'monospace',
        }}>
          <strong>Render error:</strong>
          <pre style={{ marginTop: '0.5rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
            {renderError}
          </pre>
        </div>
      )}
      <div ref={containerRef} style={{ opacity: isRendering ? 0.3 : 1, transition: 'opacity 0.2s' }} />
    </div>
  );
}
