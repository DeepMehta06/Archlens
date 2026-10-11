import { useState } from 'react';
import { Check, Copy, MessageSquareText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

export function DraftMessageCard({ language, text }: { language: 'english' | 'hinglish'; text: string }) {
  const [value, setValue] = useState(text);
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="glass-panel rounded-lg p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-ink">
          <MessageSquareText className="size-4 text-brand" />
          Draft message ({language === 'hinglish' ? 'Hinglish' : 'English'})
        </div>
        <Button size="xs" variant="outline" onClick={copy}>
          {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
      <Textarea value={value} onChange={(e) => setValue(e.target.value)} className="min-h-28 bg-background/60 text-sm" />
      <p className="mt-1.5 text-xs text-muted-foreground">Edit freely — nothing is sent anywhere until you copy and send it yourself.</p>
    </div>
  );
}
