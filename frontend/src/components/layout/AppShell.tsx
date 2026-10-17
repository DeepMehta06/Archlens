import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Download, ExternalLink, Loader2, PanelLeft, PanelRight } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent } from '@/components/ui/sheet';
import { SourcesRail } from './SourcesRail';
import { WorkspacePanel } from './WorkspacePanel';
import { ChatPanel } from '@/components/chat/ChatPanel';
import { api, ApiError } from '@/lib/api';
import type { Project } from '@/lib/types';
import logo from '@/assets/archlens-logo.png';

export function AppShell({ project }: { project: Project }) {
  const [railOpen, setRailOpen] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [exportingNotion, setExportingNotion] = useState(false);

  const exportToNotion = async () => {
    setExportingNotion(true);
    try {
      const result = await api.exportNotion(project.id);
      toast.success('Exported to Notion', {
        description: 'Open the page',
        action: { label: 'Open', onClick: () => window.open(result.url, '_blank') },
      });
    } catch (err) {
      if (err instanceof ApiError && err.status === 501) {
        toast.error('Notion isn’t configured on this server yet.');
      } else {
        toast.error(err instanceof ApiError ? err.message : 'Could not export to Notion.');
      }
    } finally {
      setExportingNotion(false);
    }
  };

  const handleSourceAdded = () => {
    // sources rail polls on its own; nothing else needed here
  };

  return (
    <div className="flex h-screen flex-col">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border/70 bg-background/60 px-4 backdrop-blur-sm md:px-6">
        <div className="flex items-center gap-3">
          <Button size="icon-sm" variant="ghost" className="lg:hidden" onClick={() => setRailOpen(true)} aria-label="Show sources">
            <PanelLeft className="size-4" />
          </Button>
          <Link to="/">
            <img src={logo} alt="ArchLens" className="h-7 w-auto" />
          </Link>
          <span className="hidden text-sm text-ink-soft md:inline">{project.name}</span>
        </div>
        <div className="flex items-center gap-1">
          <Button size="sm" variant="outline" onClick={() => window.open(api.exportUrl(project.id), '_blank')} title="Opens the scope brief as Markdown — use your browser's print dialog to save it as PDF">
            <Download className="size-3.5" />
            <span className="hidden sm:inline">Export</span>
          </Button>
          <Button size="sm" variant="outline" onClick={exportToNotion} disabled={exportingNotion} title="Export the scope brief to Notion">
            {exportingNotion ? <Loader2 className="size-3.5 animate-spin" /> : <ExternalLink className="size-3.5" />}
            <span className="hidden sm:inline">Notion</span>
          </Button>
          <Button size="icon-sm" variant="ghost" className="xl:hidden" onClick={() => setPanelOpen(true)} aria-label="Show workspace">
            <PanelRight className="size-4" />
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <div className="hidden h-full min-h-0 lg:flex">
          <SourcesRail projectId={project.id} />
        </div>
        <Sheet open={railOpen} onOpenChange={setRailOpen}>
          <SheetContent side="left" className="w-80 p-0">
            <SourcesRail projectId={project.id} />
          </SheetContent>
        </Sheet>

        <ChatPanel projectId={project.id} onSourceAdded={handleSourceAdded} />

        <div className="hidden h-full min-h-0 xl:flex">
          <WorkspacePanel projectId={project.id} />
        </div>
        <Sheet open={panelOpen} onOpenChange={setPanelOpen}>
          <SheetContent side="right" className="w-80 p-0">
            <WorkspacePanel projectId={project.id} />
          </SheetContent>
        </Sheet>
      </div>
    </div>
  );
}
