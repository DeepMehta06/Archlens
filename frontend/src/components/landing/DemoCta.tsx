import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { api } from '@/lib/api';
import type { Project } from '@/lib/types';

export function DemoCta({ className }: { className?: string }) {
  const navigate = useNavigate();
  const [state, setState] = useState<'idle' | 'seeding' | 'processing'>('idle');
  const [progress, setProgress] = useState(0);
  const [stage, setStage] = useState<string | null>(null);

  const run = async () => {
    setState('seeding');
    try {
      const result = await api.demoSeed();
      if (!result.job) {
        navigate(`/project/${result.project.id}`);
        return;
      }
      setState('processing');
      await pollJob(result.job.id, result.project);
    } catch {
      setState('idle');
    }
  };

  const pollJob = (jobId: string, project: Project) =>
    new Promise<void>((resolve) => {
      const interval = setInterval(async () => {
        const job = await api.getJob(jobId);
        setProgress(job.progress);
        setStage(job.stage);
        if (job.status === 'completed' || job.status === 'failed') {
          clearInterval(interval);
          resolve();
          navigate(`/project/${project.id}`);
        }
      }, 1000);
    });

  if (state === 'idle') {
    return (
      <Button size="lg" onClick={run} className={className}>
        Try the demo
        <ArrowRight className="size-4" />
      </Button>
    );
  }

  return (
    <div className={className}>
      <div className="flex items-center gap-2 text-sm text-ink-soft">
        <Loader2 className="size-4 animate-spin" />
        {state === 'seeding' ? 'Loading a sample project…' : (stage ?? 'Analyzing the conversation…')}
      </div>
      <Progress value={state === 'seeding' ? 10 : progress} className="mt-2 w-56" />
    </div>
  );
}
