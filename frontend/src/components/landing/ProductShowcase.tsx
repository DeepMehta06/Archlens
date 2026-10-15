import { FileStack, Inbox, Workflow } from 'lucide-react';
import CardSwap, { Card } from './CardSwap';
import { Badge } from '@/components/ui/badge';
import { MermaidDiagram } from '@/components/chat/MermaidDiagram';

const DIAGRAM_SOURCE = `sequenceDiagram
  participant P as Patient
  participant B as Booking App
  participant D as Doctor
  P->>B: Request appointment
  B->>D: Submit for approval
  D-->>B: Approve booking
  B-->>P: Confirm + WhatsApp reminder`;

function ShowcaseHeader({ icon: Icon, label }: { icon: typeof FileStack; label: string }) {
  return (
    <div className="flex items-center gap-2 border-b border-border px-4 py-3">
      <Icon className="size-4 text-accent" />
      <span className="text-sm font-semibold text-ink">{label}</span>
    </div>
  );
}

export function ProductShowcase() {
  return (
    <section className="w-full bg-ink py-24">
      <div className="mx-auto grid max-w-[1400px] gap-10 px-6 lg:grid-cols-2 lg:items-center lg:gap-16 lg:px-12">
        <div>
          <span className="inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-white/70">What it produces</span>
          <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">From an empty project to a diagram you can hand off.</h2>
          <p className="mt-4 max-w-md text-base leading-relaxed text-white/60">
            A project starts empty. As the conversation gets parsed, you get a cited ledger, a verified evidence trail,
            and architecture diagrams generated from what was actually agreed.
          </p>
        </div>

        <div className="relative h-[460px]">
          <CardSwap width={360} height={260} cardDistance={50} verticalDistance={58} depth={70} skewAmount={4} visibleCards={4} delay={3400} theme="light" cardRadius={16}>
            <Card>
              <ShowcaseHeader icon={Inbox} label="Empty project" />
              <div className="flex h-[calc(100%-45px)] flex-col items-center justify-center gap-2 px-6 text-center">
                <p className="text-sm text-ink-soft">No sources yet.</p>
                <p className="text-xs text-ink-soft">Paste a client conversation to start building the ledger.</p>
              </div>
            </Card>

            <Card>
              <ShowcaseHeader icon={FileStack} label="Ledger items (8)" />
              <div className="flex flex-col gap-1.5 p-3">
                {[
                  { id: 'REQ-001', title: 'Book appointments online', badge: 'Approved' },
                  { id: 'REQ-003', title: 'UPI advance payment', badge: 'Approved' },
                  { id: 'ASM-001', title: 'Cash payment option', badge: 'Needs review' },
                ].map((r) => (
                  <div key={r.id} className="flex items-center justify-between gap-2 rounded border border-border px-2 py-1.5 text-xs">
                    <span className="truncate text-ink">{r.title}</span>
                    <Badge variant={r.badge === 'Approved' ? 'verified' : 'caution'} className="shrink-0 px-1.5 py-0 text-[0.6rem]">
                      {r.badge}
                    </Badge>
                  </div>
                ))}
              </div>
            </Card>

            <Card>
              <ShowcaseHeader icon={FileStack} label="Evidence, verified" />
              <div className="flex h-[calc(100%-45px)] flex-col gap-2 p-4">
                <p className="text-xs leading-relaxed text-ink">"UPI se lena hai, advance payment chahiye booking ke time"</p>
                <Badge variant="verified" className="w-fit">
                  Verified
                </Badge>
                <p className="mt-auto text-[0.65rem] text-ink-soft">DEMO DATA: clinic WhatsApp chat</p>
              </div>
            </Card>

            <Card>
              <ShowcaseHeader icon={Workflow} label="Diagram, generated" />
              <div className="h-[calc(100%-45px)] overflow-hidden p-2">
                <MermaidDiagram source={DIAGRAM_SOURCE} id="showcase-sequence" />
              </div>
            </Card>
          </CardSwap>
        </div>
      </div>
    </section>
  );
}
