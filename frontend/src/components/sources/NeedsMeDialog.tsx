import { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { Source } from '@/lib/types';

export function NeedsMeDialog({ source, onResolve, onDismiss }: { source: Source | null; onResolve: (me: string) => void; onDismiss: () => void }) {
  const [me, setMe] = useState('');

  return (
    <Dialog open={Boolean(source)} onOpenChange={(open) => !open && onDismiss()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Which sender is you?</DialogTitle>
          <DialogDescription>We couldn't tell which side of "{source?.label ?? 'this conversation'}" is you. This decides whose statements count as the client's.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="me-name">Your name, as it appears in the chat</Label>
          <Input id="me-name" value={me} onChange={(e) => setMe(e.target.value)} placeholder="e.g. Riya" autoFocus />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onDismiss}>
            Skip for now
          </Button>
          <Button
            onClick={() => {
              if (me.trim()) onResolve(me.trim());
            }}
            disabled={!me.trim()}
          >
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
