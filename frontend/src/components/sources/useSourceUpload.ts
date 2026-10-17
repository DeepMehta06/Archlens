import { useCallback, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { api, ApiError } from '@/lib/api';
import { validateFile } from '@/lib/uploads';
import type { Source } from '@/lib/types';

const JOB_STAGE_LABEL: Record<string, string> = {
  transcribing: 'Transcribing',
  indexing: 'Indexing',
};

function stageLabel(stage: string | null): string {
  if (!stage) return 'Working…';
  if (JOB_STAGE_LABEL[stage]) return JOB_STAGE_LABEL[stage];
  if (stage.startsWith('extracting')) return `Extracting (${stage.replace('extracting', '').trim()})`;
  return stage;
}

export function useSourceUpload(projectId: string) {
  const queryClient = useQueryClient();
  const [activeCount, setActiveCount] = useState(0);
  const [needsMeSource, setNeedsMeSource] = useState<Source | null>(null);
  const intervalsRef = useRef<Set<ReturnType<typeof setInterval>>>(new Set());

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['sources', projectId] });
    queryClient.invalidateQueries({ queryKey: ['ledger', projectId] });
  }, [queryClient, projectId]);

  const pollJob = useCallback(
    (jobId: string, source: Source, toastId: string | number) => {
      // Each upload gets its own interval — concurrent uploads must not cancel each other's polling.
      const interval = setInterval(async () => {
        try {
          const job = await api.getJob(jobId);
          if (job.status === 'processing' || job.status === 'queued') {
            toast.loading(stageLabel(job.stage), { id: toastId, description: source.label ?? undefined });
            return;
          }
          intervalsRef.current.delete(interval);
          clearInterval(interval);
          setActiveCount((n) => Math.max(0, n - 1));
          invalidate();
          if (job.status === 'completed') {
            toast.success('Source added', { id: toastId, description: source.label ?? undefined });
            if (source.metadata_json?.needs_me) setNeedsMeSource(source);
          } else {
            toast.error(job.error_message ?? 'Could not process that file.', { id: toastId });
          }
        } catch {
          intervalsRef.current.delete(interval);
          clearInterval(interval);
          setActiveCount((n) => Math.max(0, n - 1));
          toast.error('Lost track of that upload — check Sources for its status.', { id: toastId });
        }
      }, 1000);
      intervalsRef.current.add(interval);
    },
    [invalidate],
  );

  const uploadFile = useCallback(
    async (file: File) => {
      const result = validateFile(file);
      if (!result.ok) {
        toast.error(`${file.name}: ${result.message}`);
        return;
      }

      setActiveCount((n) => n + 1);
      const toastId = toast.loading(`Uploading ${file.name}…`);
      try {
        const { source, job } = await api.uploadSource(projectId, file);
        invalidate();
        pollJob(job.id, source, toastId);
      } catch (err) {
        setActiveCount((n) => Math.max(0, n - 1));
        toast.error(err instanceof ApiError ? err.message : 'Upload failed.', { id: toastId });
      }
    },
    [projectId, invalidate, pollJob],
  );

  const uploadFiles = useCallback(
    (files: FileList | File[]) => {
      Array.from(files).forEach((file) => uploadFile(file));
    },
    [uploadFile],
  );

  const connectGithub = useCallback(
    async (repo: string, ref?: string) => {
      setActiveCount((n) => n + 1);
      const toastId = toast.loading(`Connecting ${repo}…`);
      try {
        const { source, job } = await api.connectGithubSource(projectId, { repo, ref: ref || undefined });
        invalidate();
        pollJob(job.id, source, toastId);
        return true;
      } catch (err) {
        setActiveCount((n) => Math.max(0, n - 1));
        toast.error(err instanceof ApiError ? err.message : 'Could not connect that repo.', { id: toastId });
        return false;
      }
    },
    [projectId, invalidate, pollJob],
  );

  const resolveNeedsMe = useCallback(
    async (me: string) => {
      if (!needsMeSource) return;
      try {
        await api.updateSource(projectId, needsMeSource.id, { me });
        invalidate();
        toast.success('Got it.');
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : 'Could not save that.');
      } finally {
        setNeedsMeSource(null);
      }
    },
    [projectId, needsMeSource, invalidate],
  );

  return {
    uploadFile,
    uploadFiles,
    connectGithub,
    uploading: activeCount > 0,
    activeCount,
    needsMeSource,
    resolveNeedsMe,
    dismissNeedsMe: () => setNeedsMeSource(null),
  };
}
