import { ArrowRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

const BEFORE = [
  { text: 'UPI se lena hai, advance payment chahiye booking ke time', time: '10:12' },
  { text: 'Cash at clinic bhi allow kar sakte hain shayad, abhi pakka nahi hai', time: '10:14' },
  { text: 'Doctor approve karega, har booking confirm hone se pehle', time: '10:16' },
];

export function SolutionSection() {
  return (
    <section className="w-full bg-ink py-24">
      <div className="mx-auto max-w-[1400px] px-6 text-center lg:px-12">
        <span className="inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-white/70">The solution</span>
        <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">ArchLens turns chat into a cited ledger.</h2>
        <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-white/60">
          Every item names the exact words it came from, stays "needs review" until you approve it, and keeps the
          certainty separate from the approval.
        </p>
      </div>

      <div className="mx-auto mt-12 grid max-w-[1400px] items-center gap-6 px-6 lg:grid-cols-[1fr_auto_1fr] lg:gap-8 lg:px-12">
        <div className="overflow-hidden rounded-2xl border border-border bg-background shadow-xl">
          <div className="flex items-center gap-2 border-b border-border bg-canvas-deep/50 px-4 py-2.5">
            <span className="text-xs font-semibold text-ink-soft">Before</span>
            <span className="text-xs text-ink-soft">— pasted WhatsApp export</span>
          </div>
          <div className="flex flex-col gap-2 p-4">
            {BEFORE.map((m) => (
              <div key={m.text} className="rounded-xl rounded-tl-sm bg-canvas-deep/60 px-3 py-2 text-sm text-ink">
                {m.text}
                <span className="ml-2 text-[0.65rem] text-ink-soft">{m.time}</span>
              </div>
            ))}
          </div>
        </div>

        <ArrowRight className="mx-auto hidden size-6 shrink-0 rotate-90 text-white/50 lg:block lg:rotate-0" />

        <div className="overflow-hidden rounded-2xl border border-border bg-background shadow-xl">
          <div className="flex items-center gap-2 border-b border-border bg-canvas-deep/50 px-4 py-2.5">
            <span className="text-xs font-semibold text-ink-soft">After</span>
            <span className="text-xs text-ink-soft">— structured, cited, reviewable</span>
          </div>
          <div className="p-4">
            <div className="flex items-center gap-2">
              <span className="font-mono-id rounded bg-canvas-deep px-1.5 py-0.5 text-xs text-ink-soft">REQ-003</span>
              <Badge variant="caution">Needs review</Badge>
              <Badge variant="verified">Explicit</Badge>
            </div>
            <p className="mt-2 text-sm font-medium text-ink">Advance payment required via UPI</p>
            <p className="mt-1 text-xs leading-relaxed text-ink-soft">
              The platform should require UPI payment in advance at the time of booking.
            </p>
            <div className="mt-3 rounded-lg bg-canvas-deep/50 p-2.5 text-xs text-ink-soft">
              "UPI se lena hai, advance payment chahiye booking ke time"
              <div className="mt-1 text-[0.65rem]">— DEMO DATA: clinic WhatsApp chat, 10:12</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
