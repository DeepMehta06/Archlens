import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { AppShell } from '@/components/layout/AppShell';

export function Workspace() {
  const { id } = useParams<{ id: string }>();
  const { data: project, isLoading, isError } = useQuery({
    queryKey: ['project', id],
    queryFn: () => api.getProject(id!),
    enabled: Boolean(id),
  });

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center gap-2 text-ink-soft">
        <Loader2 className="size-4 animate-spin" />
        Loading project…
      </div>
    );
  }

  if (isError || !project) {
    return (
      <div className="flex h-screen items-center justify-center text-ink-soft">
        We couldn't find that project.
      </div>
    );
  }

  return <AppShell project={project} />;
}
