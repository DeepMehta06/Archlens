import { useRef, useState, type KeyboardEvent } from 'react';
import { ArrowUp, Paperclip } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { ACCEPT_ATTR, UPLOAD_TOOLTIP } from '@/lib/uploads';

export function ChatComposer({ onSend, onAttach, disabled }: { onSend: (text: string) => void; onAttach: (files: FileList) => void; disabled: boolean }) {
  const [value, setValue] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const submit = () => {
    const text = value.trim();
    if (!text || disabled) return;
    onSend(text);
    setValue('');
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="glass-panel-strong flex items-end gap-2 rounded-2xl p-2 shadow-sm">
      <input
        ref={fileInputRef}
        type="file"
        accept={ACCEPT_ATTR}
        multiple
        className="hidden"
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) onAttach(e.target.files);
          e.target.value = '';
        }}
      />
      <Button size="icon" variant="ghost" onClick={() => fileInputRef.current?.click()} disabled={disabled} aria-label="Attach a file" title={UPLOAD_TOOLTIP}>
        <Paperclip className="size-4" />
      </Button>
      <Textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Paste a client chat, ask about the ledger, or request a diagram…"
        className="min-h-10 max-h-40 resize-none border-none bg-transparent px-2 py-2 shadow-none focus-visible:ring-0"
      />
      <Button size="icon" onClick={submit} disabled={disabled || !value.trim()} aria-label="Send message">
        <ArrowUp className="size-4" />
      </Button>
    </div>
  );
}
