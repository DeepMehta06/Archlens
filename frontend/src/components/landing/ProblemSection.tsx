import { FileQuestion, MessagesSquare, RefreshCw, Ban } from 'lucide-react';
import meetingPhoto from '@/assets/meeting-preparation.jpg';
import FolderFloat from './FolderFloat';

const SYMPTOMS = [
  { icon: MessagesSquare, label: 'Scattered across chats' },
  { icon: FileQuestion, label: 'Unclear requirements' },
  { icon: Ban, label: 'Missing context' },
  { icon: RefreshCw, label: 'Constant changes' },
];

const FEEDBACK_NOTES = ['Can we also add COD?', 'Need invoice in PDF', 'Actually make it multi-vendor', 'What about refunds?', 'Also need a seller dashboard', 'Can it integrate with our system?'];

export function ProblemSection() {
  return (
    <section className="w-full bg-canvas py-24">
      <div className="mx-auto grid max-w-[1400px] gap-12 px-6 lg:grid-cols-2 lg:items-center lg:gap-16 lg:px-12">
        <div>
          <span className="inline-flex items-center rounded-full bg-canvas-deep px-3 py-1 text-xs font-medium text-ink-soft">
            The problem
          </span>
          <h2 className="mt-4 text-3xl font-extrabold tracking-tight text-ink sm:text-4xl">
            Important requirements get lost in messy conversations.
          </h2>
          <p className="mt-4 max-w-md text-base leading-relaxed text-ink-soft">
            Client discussions happen across WhatsApp, calls and emails. Key details get scattered, misread or
            forgotten — and that's where scope confusion, rework and unhappy clients start.
          </p>
          <ul className="mt-6 grid grid-cols-2 gap-3">
            {SYMPTOMS.map((s) => (
              <li key={s.label} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-sm text-ink-soft">
                <s.icon className="size-4 shrink-0 text-accent" />
                {s.label}
              </li>
            ))}
          </ul>
        </div>

        <div className="relative">
          <div className="overflow-hidden rounded-2xl border border-border shadow-xl shadow-ink/10">
            <img src={meetingPhoto} alt="A team discussing a client's requirements around a table" className="aspect-[4/3] w-full object-cover" />
          </div>
          <div className="absolute -bottom-10 -right-6 hidden sm:block">
            <FolderFloat
              items={FEEDBACK_NOTES}
              label="Client feedback"
              trigger="hover"
              physics
              drift={0.6}
              width={180}
              height={132}
              folderColor="#1c1a2b"
              frontColor="#2a273d"
              paperColor="#ffffff"
              itemColor="#ffffff"
              itemTextColor="#15131f"
              labelColor="#ffffff"
            />
          </div>
        </div>
      </div>
    </section>
  );
}
