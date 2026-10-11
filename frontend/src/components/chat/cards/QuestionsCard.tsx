import { HelpCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { Question } from '@/lib/types';

const priorityVariant = { low: 'outline', medium: 'caution', high: 'danger' } as const;

export function QuestionsCard({ questions }: { questions: Question[] }) {
  if (questions.length === 0) {
    return <p className="text-sm text-muted-foreground">No open questions.</p>;
  }

  return (
    <div className="glass-panel rounded-lg p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-ink">
        <HelpCircle className="size-4 text-brand" />
        Questions for the client ({questions.length})
      </div>
      <ul className="flex flex-col gap-2">
        {questions.map((q) => (
          <li key={q.id} className="rounded-md border border-border bg-background/60 p-2.5">
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-medium text-ink">{q.question}</p>
              <Badge variant={priorityVariant[q.priority]}>{q.priority}</Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">{q.reason}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
