import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Check, Loader2, MessageSquareText, X } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { DraftMessageCard } from '@/components/chat/cards/DraftMessageCard';
import { api } from '@/lib/api';

const PRIORITY_VARIANT = { low: 'outline', medium: 'caution', high: 'danger' } as const;

export function QuestionsTab({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<{ language: 'english' | 'hinglish'; text: string } | null>(null);
  const [drafting, setDrafting] = useState<'english' | 'hinglish' | null>(null);

  const { data: questions, isLoading } = useQuery({
    queryKey: ['questions', projectId],
    queryFn: () => api.listQuestions(projectId, 'open'),
  });

  const resolve = useMutation({
    mutationFn: (vars: { id: string; status: 'resolved' | 'dismissed' }) => api.updateQuestion(vars.id, { status: vars.status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['questions', projectId] }),
  });

  const runDraft = async (language: 'english' | 'hinglish') => {
    setDrafting(language);
    try {
      const result = await api.draftMessage(projectId, { language, question_ids: questions?.map((q) => q.id) });
      setDraft({ language, text: result.text });
    } finally {
      setDrafting(null);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ScrollArea className="min-h-0 flex-1 overflow-hidden px-3 py-3">
        {isLoading && (
          <div className="flex items-center gap-2 px-1 py-3 text-xs text-ink-soft">
            <Loader2 className="size-3.5 animate-spin" />
            Loading questions…
          </div>
        )}
        {!isLoading && questions?.length === 0 && <p className="px-1 py-3 text-xs text-ink-soft">No open questions. Nice and clear.</p>}

        <ul className="flex flex-col gap-2">
          {questions?.map((q) => (
            <li key={q.id} className="rounded-lg border border-border bg-background/60 p-2.5">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-ink">{q.question}</p>
                <Badge variant={PRIORITY_VARIANT[q.priority]}>{q.priority}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{q.reason}</p>
              <div className="mt-2 flex gap-1.5">
                <Button size="xs" variant="outline" onClick={() => resolve.mutate({ id: q.id, status: 'resolved' })} disabled={resolve.isPending}>
                  <Check className="size-3" />
                  Resolved
                </Button>
                <Button size="xs" variant="ghost" onClick={() => resolve.mutate({ id: q.id, status: 'dismissed' })} disabled={resolve.isPending}>
                  <X className="size-3" />
                  Dismiss
                </Button>
              </div>
            </li>
          ))}
        </ul>

        {draft && (
          <div className="mt-3">
            <DraftMessageCard language={draft.language} text={draft.text} />
          </div>
        )}
      </ScrollArea>

      {questions && questions.length > 0 && (
        <div className="flex gap-2 border-t border-border/70 p-3">
          <Button size="sm" variant="outline" className="flex-1" onClick={() => runDraft('english')} disabled={drafting !== null}>
            {drafting === 'english' ? <Loader2 className="size-3.5 animate-spin" /> : <MessageSquareText className="size-3.5" />}
            Draft (English)
          </Button>
          <Button size="sm" variant="outline" className="flex-1" onClick={() => runDraft('hinglish')} disabled={drafting !== null}>
            {drafting === 'hinglish' ? <Loader2 className="size-3.5 animate-spin" /> : <MessageSquareText className="size-3.5" />}
            Draft (Hinglish)
          </Button>
        </div>
      )}
    </div>
  );
}
