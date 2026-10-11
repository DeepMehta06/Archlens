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
  a.click();
  URL.revokeObjectURL(url);
}

function downloadSvg(svg: string, filename: string) {
  downloadBlob(new Blob([svg], { type: 'image/svg+xml' }), filename);
}

function downloadPng(svg: string, filename: string) {
  const dims = svg.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  const width = dims ? Math.ceil(parseFloat(dims[1])) : 1200;
  const height = dims ? Math.ceil(parseFloat(dims[2])) : 800;
  const scale = 2;

  const svgBlob = new Blob([svg], { type: 'image/svg+xml' });
  const url = URL.createObjectURL(svgBlob);
  const img = new window.Image();
  img.onload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = width * scale;
    canvas.height = height * scale;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.fillStyle = '#ffffff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.scale(scale, scale);
      ctx.drawImage(img, 0, 0, width, height);
      canvas.toBlob((blob) => {
        if (blob) downloadBlob(blob, filename);
        URL.revokeObjectURL(url);
      }, 'image/png');
    }
  };
  img.src = url;
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
  const [svg, setSvg] = useState<string | null>(null);
  const filenameBase = slugify(title);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <div id="diagram-print-area" className="print-area rounded-lg border border-border bg-white p-4">
          <MermaidDiagram source={mermaidSource} id={`focus-${diagramId}`} onSvgReady={setSvg} />
        </div>

        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" disabled={!svg} onClick={() => svg && downloadSvg(svg, `${filenameBase}.svg`)}>
            <Download className="size-3.5" />
            Download SVG
          </Button>
          <Button size="sm" variant="outline" disabled={!svg} onClick={() => svg && downloadPng(svg, `${filenameBase}.png`)}>
            <ImageIcon className="size-3.5" />
            Download PNG
          </Button>
          <Button size="sm" variant="outline" onClick={() => window.print()}>
            <Printer className="size-3.5" />
            Save as PDF
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
