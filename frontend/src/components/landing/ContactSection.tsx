import { Mail, ArrowUpRight } from 'lucide-react';
import { SpotlightCard } from './SpotlightCard';

const EMAIL = 'deepmehta2006@gmail.com';

export function ContactSection() {
  return (
    <section className="w-full bg-ink py-24">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <SpotlightCard
          spotlightColor="rgba(255, 255, 255, 0.12)"
          className="mx-auto flex max-w-3xl flex-col items-center gap-6 px-8 py-16 text-center sm:px-16"
        >
          <span className="inline-flex items-center rounded-full bg-white/10 px-3 py-1 text-xs font-medium text-white/70">
            Get in touch
          </span>
          <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
            Questions, feedback, or just want to talk about it?
          </h2>
          <p className="max-w-md text-base leading-relaxed text-white/60">
            ArchLens is built and maintained by Deep Mehta. Reach out any time — I read every message.
          </p>

          <div className="mt-2 flex flex-wrap items-center justify-center gap-3">
            <a
              href={`mailto:${EMAIL}`}
              className="group inline-flex items-center gap-2 rounded-full bg-white px-5 py-2.5 text-sm font-semibold text-ink transition-colors hover:bg-white/90"
            >
              <Mail className="size-4" />
              {EMAIL}
              <ArrowUpRight className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
            </a>
          </div>
        </SpotlightCard>

        <p className="mt-10 text-center text-xs text-white/40">Made by Deep Mehta</p>
      </div>
    </section>
  );
}
