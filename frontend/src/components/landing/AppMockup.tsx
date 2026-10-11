import { FileStack, GitBranch, HelpCircle, MessageCircle, Workflow, BookOpenCheck } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

const SOURCES = [
  { label: 'DEMO DATA: clinic WhatsApp chat', status: 'Processed' },
  { label: 'Incoming request', status: 'Processed' },
];

const LEDGER_PREVIEW = [
  { id: 'REQ-001', title: 'Patients must be able to book appointments online', approval: 'Approved', evidence: 'Explicit' },
  { id: 'REQ-003', title: 'Advance payment required via UPI', approval: 'Approved', evidence: 'Explicit' },
  { id: 'ASM-001', title: 'Cash payment option might be included later', approval: 'Needs review', evidence: 'Tentative' },
];

export function AppMockup() {
  return (
    <div className="overflow-hidden rounded-xl border border-border shadow-2xl shadow-ink/10">
      <div className="flex items-center gap-1.5 border-b border-border bg-canvas-deep/60 px-3 py-2.5">
        <span className="size-2.5 rounded-full bg-[#ff5f57]" />
        <span className="size-2.5 rounded-full bg-[#febc2e]" />
        <span className="size-2.5 rounded-full bg-[#28c840]" />
        <span className="ml-3 text-xs text-ink-soft">archlens.app/project/pune-clinic-app</span>
      </div>

      <div className="flex h-[360px] bg-background text-left sm:h-[420px]">
        <div className="hidden w-40 shrink-0 border-r border-border p-3 sm:block">
          <p className="text-[0.65rem] font-semibold tracking-wide text-ink-soft">SOURCES</p>
          <div className="mt-2 flex flex-col gap-1.5">
            {SOURCES.map((s) => (
              <div key={s.label} className="rounded-md border border-border p-1.5">
                <p className="flex items-center gap-1 text-[0.65rem] font-medium text-ink">
                  <MessageCircle className="size-2.5 text-accent" />
                  <span className="truncate">{s.label}</span>
                </p>
                <Badge variant="verified" className="mt-1 px-1.5 py-0 text-[0.55rem]">
                  {s.status}
                </Badge>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-1 flex-col justify-end gap-2 p-3">
          <div className="flex justify-end">
            <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-ink px-3 py-2 text-[0.7rem] text-white">
              Bhai, also we need refund within 7 days if the paneer is cold 😅
            </div>
          </div>
          <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-border bg-canvas-deep/50 px-3 py-2 text-[0.7rem] text-ink">
            Got it. I'll add a <span className="rounded bg-accent-soft px-1 font-mono-id text-[0.6rem] text-accent-deep">[C4]</span> refund policy item — 7-day
            window, triggered by quality complaints.
          </div>
          <div className="rounded-lg border border-border bg-background p-2.5">
            <p className="mb-1.5 flex items-center gap-1 text-[0.65rem] font-semibold text-ink">
              <FileStack className="size-3 text-accent" />
              Ledger items (8)
            </p>
            <div className="flex flex-col gap-1">
              {LEDGER_PREVIEW.map((item) => (
                <div key={item.id} className="flex items-center justify-between gap-2 rounded border border-border/70 px-1.5 py-1">
                  <div className="min-w-0">
                    <span className="font-mono-id mr-1.5 rounded bg-canvas-deep px-1 py-px text-[0.55rem] text-ink-soft">{item.id}</span>
                    <span className="truncate text-[0.62rem] text-ink">{item.title}</span>
                  </div>
                  <Badge variant={item.approval === 'Approved' ? 'verified' : 'caution'} className="shrink-0 px-1.5 py-0 text-[0.55rem]">
                    {item.approval}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="hidden w-36 shrink-0 border-l border-border p-3 lg:block">
          <div className="mb-3 flex items-center gap-2 text-ink-soft">
            <FileStack className="size-3.5 text-accent" />
            <Workflow className="size-3.5" />
            <HelpCircle className="size-3.5" />
            <GitBranch className="size-3.5" />
            <BookOpenCheck className="size-3.5" />
          </div>
          <p className="text-[0.65rem] font-semibold tracking-wide text-ink-soft">EVIDENCE</p>
          <div className="mt-2 rounded-md border border-border p-2">
            <p className="text-[0.6rem] leading-relaxed text-ink">"Cash at clinic bhi allow kar sakte hain shayad, abhi pakka nahi hai"</p>
            <Badge variant="verified" className="mt-1.5 px-1.5 py-0 text-[0.55rem]">
              Verified
            </Badge>
          </div>
        </div>
      </div>
    </div>
  );
}
