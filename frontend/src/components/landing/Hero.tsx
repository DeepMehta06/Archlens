import { Check, Sparkle } from 'lucide-react';
import { DemoCta } from './DemoCta';
import { AppMockup } from './AppMockup';
import BlurText from './BlurText';

const TRUST = ['Runs locally with Ollama', 'Your data stays private', 'Every quote cites its source'];

export function Hero({ onNewProject }: { onNewProject: () => void }) {
  return (
    <section className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-x-0 top-0 -z-10 h-[420px] bg-gradient-to-b from-accent-soft/60 via-accent-soft/15 to-transparent" />

      <div className="mx-auto flex max-w-4xl flex-col items-center px-6 pt-20 pb-16 text-center sm:pt-28">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-3 py-1 text-xs font-medium text-ink-soft">
          <Sparkle className="size-3 text-accent" />
          Local. Private. Built from real client chats.
        </span>

        <h1 className="mt-6 text-5xl font-extrabold leading-[1.08] tracking-tight text-ink sm:text-6xl lg:text-7xl">
          <span className="sr-only">From client chats to a scope you can defend.</span>
          <div aria-hidden="true">
            <BlurText
              text="From client chats to a scope you can defend."
              animateBy="words"
              direction="top"
              delay={90}
              stepDuration={0.4}
              className="justify-center"
            />
          </div>
        </h1>

        <p className="mt-5 max-w-xl text-base leading-relaxed text-ink-soft sm:text-lg">
          Paste a client conversation — English, Hinglish, a WhatsApp export — and ArchLens turns it into a
          requirement ledger where every line cites the exact words it came from.
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <DemoCta />
          <button
            onClick={onNewProject}
            className="rounded-md border border-border px-4 py-2 text-sm font-medium text-ink transition-colors hover:bg-canvas-deep"
          >
            Start a new project
          </button>
        </div>

        <ul className="mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-ink-soft">
          {TRUST.map((t) => (
            <li key={t} className="flex items-center gap-1.5">
              <Check className="size-3.5 text-verified" />
              {t}
            </li>
          ))}
        </ul>
      </div>

      <div className="mx-auto max-w-6xl px-6 pb-20 lg:px-12">
        <AppMockup />
      </div>
    </section>
  );
}
