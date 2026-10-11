import { AlertTriangle } from 'lucide-react';

export function ErrorCard({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 rounded-lg bg-danger-soft px-3 py-2.5 text-sm text-danger">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}
