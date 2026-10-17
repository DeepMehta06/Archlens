import { useRef, useState } from 'react';
import { useGSAP } from '@gsap/react';
import gsap from 'gsap';
import { Loader2 } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

export function GithubConnectDialog({
  open,
  onOpenChange,
  onConnect,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConnect: (repo: string, ref?: string) => Promise<boolean>;
}) {
  const [repo, setRepo] = useState('');
  const [ref, setRef] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      if (!open || !bodyRef.current) return;
      gsap.from(bodyRef.current, { y: 10, opacity: 0, duration: 0.35, ease: 'power2.out' });
    },
    { scope: bodyRef, dependencies: [open] },
  );

  const submit = async () => {
    if (!repo.trim()) return;
    setSubmitting(true);
    const ok = await onConnect(repo.trim(), ref.trim() || undefined);
    setSubmitting(false);
    if (ok) {
      setRepo('');
      setRef('');
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Connect a GitHub repo</DialogTitle>
          <DialogDescription>
            Read-only. Indexed as code for the implementation-brief generator — it never produces ledger items.
          </DialogDescription>
        </DialogHeader>
        <div ref={bodyRef} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gh-repo">Repository</Label>
            <Input id="gh-repo" value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="owner/repo or https://github.com/owner/repo" autoFocus />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="gh-ref">Branch or ref (optional)</Label>
            <Input id="gh-ref" value={ref} onChange={(e) => setRef(e.target.value)} placeholder="main" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!repo.trim() || submitting}>
            {submitting && <Loader2 className="size-3.5 animate-spin" />}
            Connect
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
