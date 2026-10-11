import { useState } from 'react';
import { Download, Image as ImageIcon, Printer } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { MermaidDiagram } from './MermaidDiagram';

function slugify(text: string) {
  return (
    text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)/g, '') || 'diagram'
  );
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Get a clean, self-contained SVG string from the rendered DOM element */
function getCleanSvg(containerRef: HTMLElement | null): string | null {
  const svgEl = containerRef?.querySelector('svg');
  if (!svgEl) return null;

  // Clone so we don't mutate the live element
  const clone = svgEl.cloneNode(true) as SVGElement;

  // Ensure explicit width/height for rasterisation
  const bbox = svgEl.getBoundingClientRect();
  if (!clone.getAttribute('width')) clone.setAttribute('width', String(Math.ceil(bbox.width) || 1200));
  if (!clone.getAttribute('height')) clone.setAttribute('height', String(Math.ceil(bbox.height) || 800));

  // Add white background rect so PNG isn't transparent
  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  bg.setAttribute('width', '100%');
  bg.setAttribute('height', '100%');
  bg.setAttribute('fill', 'white');
  clone.insertBefore(bg, clone.firstChild);

  return new XMLSerializer().serializeToString(clone);
}

function downloadSvg(containerRef: HTMLElement | null, filename: string) {
  const svgStr = getCleanSvg(containerRef);
  if (!svgStr) return;
  downloadBlob(new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' }), filename);
}

function downloadPng(containerRef: HTMLElement | null, filename: string) {
  const svgStr = getCleanSvg(containerRef);
  if (!svgStr) return;

  const svgEl = containerRef?.querySelector('svg');
  const bbox = svgEl?.getBoundingClientRect();
  const width = Math.ceil(bbox?.width ?? 1200);
  const height = Math.ceil(bbox?.height ?? 800);
  const scale = 2;

  const canvas = document.createElement('canvas');
  canvas.width = width * scale;
  canvas.height = height * scale;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.scale(scale, scale);

  // Encode SVG as base64 data URI to avoid browser CORS restrictions on blob URLs
  const b64 = btoa(unescape(encodeURIComponent(svgStr)));
  const dataUrl = `data:image/svg+xml;base64,${b64}`;

  const img = new window.Image();
  img.onload = () => {
    ctx.drawImage(img, 0, 0, width, height);
    canvas.toBlob((blob) => {
      if (blob) downloadBlob(blob, filename);
    }, 'image/png');
  };
  img.onerror = () => {
    // Fallback: download SVG instead if PNG rasterisation fails
    downloadSvg(containerRef, filename.replace('.png', '.svg'));
  };
  img.src = dataUrl;
}

function printDiagram(containerRef: HTMLElement | null, title: string) {
  const svgStr = getCleanSvg(containerRef);
  if (!svgStr) {
    window.print();
    return;
  }

  const printWindow = window.open('', '_blank', 'width=900,height=700');
  if (!printWindow) { window.print(); return; }

  printWindow.document.write(`<!DOCTYPE html>
<html>
<head>
  <title>${title}</title>
  <style>
    body { margin: 0; padding: 24px; font-family: sans-serif; background: white; }
    h2 { font-size: 16px; margin-bottom: 12px; color: #1c1a2b; }
    svg { max-width: 100%; height: auto; }
    @media print { body { padding: 0; } }
  </style>
</head>
<body>
  <h2>${title}</h2>
  ${svgStr}
  <script>window.onload = () => { window.print(); window.close(); }<\/script>
</body>
</html>`);
  printWindow.document.close();
}

export function DiagramViewer({
  open,
  onOpenChange,
  title,
  mermaidSource,
  diagramId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  mermaidSource: string;
  diagramId: string;
}) {
  const [containerEl, setContainerEl] = useState<HTMLElement | null>(null);
  const filenameBase = slugify(title);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <div
          id="diagram-print-area"
          className="print-area rounded-lg border border-border bg-white p-4"
          ref={setContainerEl}
        >
          <MermaidDiagram source={mermaidSource} id={`focus-${diagramId}`} />
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={!containerEl}
            onClick={() => downloadSvg(containerEl, `${filenameBase}.svg`)}
          >
            <Download className="size-3.5" />
            Download SVG
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!containerEl}
            onClick={() => downloadPng(containerEl, `${filenameBase}.png`)}
          >
            <ImageIcon className="size-3.5" />
            Download PNG
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={!containerEl}
            onClick={() => printDiagram(containerEl, title)}
          >
            <Printer className="size-3.5" />
            Save as PDF
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
