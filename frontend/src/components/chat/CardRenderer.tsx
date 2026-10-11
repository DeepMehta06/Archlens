import type { ChatCard } from '@/lib/types';
import { LedgerListCard } from './cards/LedgerListCard';
import { QuestionsCard } from './cards/QuestionsCard';
import { DraftMessageCard } from './cards/DraftMessageCard';
import { DiagramCard } from './cards/DiagramCard';
import { ChangeReportCard } from './cards/ChangeReportCard';
import { ConfirmAddSourceCard } from './cards/ConfirmAddSourceCard';
import { ErrorCard } from './cards/ErrorCard';

export function CardRenderer({ card, projectId, onSourceAdded }: { card: ChatCard; projectId: string; onSourceAdded: (jobId: string) => void }) {
  switch (card.type) {
    case 'ledger_list':
      return <LedgerListCard items={card.items} />;
    case 'questions':
      return <QuestionsCard questions={card.questions} />;
    case 'draft_message':
      return <DraftMessageCard language={card.language} text={card.text} />;
    case 'diagram':
      return <DiagramCard diagramId={card.diagram_id} title={card.title} mermaidSource={card.mermaid_source} warnings={card.warnings} />;
    case 'change_report':
      return <ChangeReportCard snapshotLabel={card.snapshot_label} results={card.results} />;
    case 'confirm_add_source':
      return <ConfirmAddSourceCard projectId={projectId} preview={card.preview} charCount={card.char_count} looksLikeWhatsapp={card.looks_like_whatsapp} onAdded={onSourceAdded} />;
    case 'error':
      return <ErrorCard message={card.message} />;
    default:
      return null;
  }
}
