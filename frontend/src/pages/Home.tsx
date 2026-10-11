import { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { InputAssessment, ProviderStatus } from '../services/api';
import { useNavigate } from 'react-router-dom';
import { Activity, FileText, ChevronRight, AlertTriangle, CheckCircle2, Circle } from 'lucide-react';

function Meter({ label, value, min, max }: { label: string; value: number; min: number; max?: number }) {
  const ok = value >= min && (max === undefined || value <= max);
  const Icon = ok ? CheckCircle2 : Circle;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: ok ? 'var(--accent-emerald)' : 'var(--text-muted)' }}>
      <Icon size={14} />
      <span>{label}: <strong>{value}</strong> / {min}</span>
    </div>
  );
}

export function Home() {
  const [name, setName] = useState('');
  const [requirements, setRequirements] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [assessment, setAssessment] = useState<InputAssessment | null>(null);
  const [providerStatus, setProviderStatus] = useState<{ active_provider: string, providers: ProviderStatus[], cloud_warning: string } | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.providerStatus()
      .then(setProviderStatus)
      .catch(err => console.error("Failed to load provider status:", err));
  }, []);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      api.assessInput(requirements)
        .then(a => { if (!cancelled) setAssessment(a); })
        .catch(err => console.error("Failed to assess input:", err));
    }, 300);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [requirements]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || !requirements.trim()) return;

    setIsSubmitting(true);
    setError(null);
    try {
      const project = await api.createProject(name, requirements);
      navigate(`/project/${project.id}`);
    } catch (err: any) {
      setError(err.message || 'Failed to create project');
      setIsSubmitting(false);
    }
  };

  const isProviderAvailable = providerStatus?.providers.some(p => p.available) ?? false;

  return (
    <div className="fade-in">
      <div style={{ textAlign: 'center', marginBottom: '3rem', marginTop: '2rem' }}>
        <h1 style={{ fontSize: '2.5rem', marginBottom: '1rem', background: 'linear-gradient(135deg, #60a5fa 0%, #a78bfa 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Understand the system before you build the system
        </h1>
        <p style={{ fontSize: '1.1rem', color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto' }}>
          Paste your messy client meeting notes, requirements, or transcripts. ArchLens extracts a structured model, finds critical gaps, and generates architecture diagrams.
        </p>
      </div>

      <div className="grid-2" style={{ maxWidth: '1000px', margin: '0 auto', gap: '2rem' }}>
        
        {/* Left Col: Form */}
        <div>
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">
                <FileText size={18} className="text-accent" />
                New Analysis
              </h2>
            </div>
            
            <form onSubmit={handleSubmit} className="form-group" style={{ gap: '1.25rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="projectName">Project Name</label>
                <input
                  id="projectName"
                  type="text"
                  className="input"
                  placeholder="e.g. Hospital Document Platform"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={isSubmitting}
                  required
                />
              </div>
              
              <div className="form-group">
                <label className="form-label" htmlFor="rawReqs">Raw Requirements / Meeting Notes</label>
                <textarea
                  id="rawReqs"
                  className="textarea"
                  placeholder="Paste everything here. Don't worry about formatting..."
                  value={requirements}
                  onChange={(e) => setRequirements(e.target.value)}
                  disabled={isSubmitting}
                  required
                  style={{ minHeight: '200px' }}
                />
                {assessment && (
                  <div style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', marginTop: '0.5rem' }}>
                    <div style={{ display: 'flex', gap: '1.25rem', flexWrap: 'wrap' }}>
                      <Meter label="Words" value={assessment.word_count} min={assessment.min_words} max={assessment.max_words} />
                      <Meter label="Requirement statements" value={assessment.statement_count} min={assessment.min_statements} />
                    </div>
                    {!assessment.is_sufficient && requirements.trim() && (
                      <div style={{ color: 'var(--text-muted)' }}>
                        {assessment.issues.join(' ')}
                      </div>
                    )}
                    {!assessment.is_sufficient && !requirements.trim() && (
                      <div style={{ color: 'var(--text-muted)' }}>
                        Needs at least {assessment.min_words} words and {assessment.min_statements} statements of what the system {assessment.accepted_keywords.slice(0, 3).join(' / ')} do.
                      </div>
                    )}
                  </div>
                )}
              </div>

              {error && (
                <div className="alert alert-error">
                  <AlertTriangle size={18} style={{ flexShrink: 0 }} />
                  {error}
                </div>
              )}

              <button 
                type="submit" 
                className="btn btn-primary" 
                disabled={isSubmitting || !name.trim() || !requirements.trim() || (!!assessment && !assessment.is_sufficient) || (!!providerStatus && !isProviderAvailable)}
                style={{ width: '100%', justifyContent: 'center', marginTop: '0.5rem' }}
              >
                {isSubmitting ? (
                  <><span className="loading-spinner" /> Analyzing Project...</>
                ) : (
                  <>Start Analysis <ChevronRight size={18} /></>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Right Col: Info/Status */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          
          <div className="card">
            <div className="card-header">
              <h3 className="card-title">
                <Activity size={18} className="text-accent" />
                System Status
              </h3>
            </div>
            
            {!providerStatus ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Checking providers...</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Active Mode</div>
                  <div className="badge badge-inferred" style={{ fontSize: '0.8rem' }}>{providerStatus.active_provider.toUpperCase()}</div>
                </div>
                
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {providerStatus.providers.map(p => (
                    <div key={p.provider} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.9rem', padding: '0.5rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span className={`provider-dot ${p.available ? 'available' : 'unavailable'}`} />
                        <span style={{ fontWeight: 500, textTransform: 'capitalize' }}>{p.provider}</span>
                      </div>
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{p.model}</span>
                    </div>
                  ))}
                </div>

                {!isProviderAvailable && (
                  <div className="alert alert-error" style={{ fontSize: '0.8rem', padding: '0.75rem' }}>
                    No AI providers are currently available. Check your backend configuration and API keys.
                  </div>
                )}
                
                {isProviderAvailable && providerStatus.cloud_warning && providerStatus.active_provider !== 'ollama' && (
                  <div className="alert alert-warning" style={{ fontSize: '0.8rem', padding: '0.75rem', marginTop: '0.5rem' }}>
                    {providerStatus.cloud_warning}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="card" style={{ background: 'linear-gradient(145deg, rgba(30,42,64,0.4) 0%, rgba(15,22,36,0.8) 100%)' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>How it works</h3>
            <ol style={{ paddingLeft: '1.2rem', color: 'var(--text-secondary)', fontSize: '0.9rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <li><strong>Extract:</strong> AI analyzes raw text to build a structured Project Model (FRs, NFRs, Entities).</li>
              <li><strong>Detect:</strong> Gap analysis identifies missing critical information.</li>
              <li><strong>Question:</strong> Generates concrete engineering questions for the client.</li>
              <li><strong>Architect:</strong> Reasons about components and decisions.</li>
              <li><strong>Visualize:</strong> Generates Mermaid diagrams (Architecture, Sequence, ER, Traceability).</li>
            </ol>
          </div>

        </div>
      </div>
    </div>
  );
}
