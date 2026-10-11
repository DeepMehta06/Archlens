import { BookOpenCheck, FileStack, GitBranch, HelpCircle, Workflow } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { LedgerTab } from '@/components/workspace/LedgerTab';
import { QuestionsTab } from '@/components/workspace/QuestionsTab';
import { BaselineTab } from '@/components/workspace/BaselineTab';
import { EvidenceTab } from '@/components/workspace/EvidenceTab';
import { DiagramsTab } from '@/components/workspace/DiagramsTab';

const TABS = [
  { value: 'ledger', label: 'Ledger', icon: FileStack },
  { value: 'diagrams', label: 'Diagrams', icon: Workflow },
  { value: 'questions', label: 'Questions', icon: HelpCircle },
  { value: 'baseline', label: 'Baseline', icon: GitBranch },
  { value: 'evidence', label: 'Evidence', icon: BookOpenCheck },
];

export function WorkspacePanel({ projectId }: { projectId: string }) {
  return (
    <aside className="flex h-full w-80 shrink-0 flex-col border-l border-border/70 bg-background/40 xl:w-96">
      <Tabs defaultValue="ledger" className="flex h-full flex-col gap-0">
        <div className="px-3 pt-3">
          <TabsList className="w-full">
            {TABS.map((tab) => (
              <TabsTrigger key={tab.value} value={tab.value} title={tab.label}>
                <tab.icon className="size-4" />
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
        <TabsContent value="ledger" className="min-h-0 flex-1">
          <LedgerTab projectId={projectId} />
        </TabsContent>
        <TabsContent value="diagrams" className="min-h-0 flex-1">
          <DiagramsTab projectId={projectId} />
        </TabsContent>
        <TabsContent value="questions" className="min-h-0 flex-1">
          <QuestionsTab projectId={projectId} />
        </TabsContent>
        <TabsContent value="baseline" className="min-h-0 flex-1">
          <BaselineTab projectId={projectId} />
        </TabsContent>
        <TabsContent value="evidence" className="min-h-0 flex-1">
          <EvidenceTab projectId={projectId} />
        </TabsContent>
      </Tabs>
    </aside>
  );
}
