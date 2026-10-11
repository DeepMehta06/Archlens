import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../services/api';
import type { Project, Diagram } from '../services/api';
import { DiagramEditor } from '../components/DiagramEditor';
import { 
  CheckCircle2, 
  HelpCircle, 
  Layers, 
  List, 
  AlertTriangle,
  RefreshCw,
  Server,
  Users
} from 'lucide-react';

export function ProjectView() {
  const { id } = useParams<{ id: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [diagrams, setDiagrams] = useState<Diagram[]>([]);
  const [activeTab, setActiveTab] = useState<'overview' | 'requirements' | 'questions' | 'architecture' | 'diagrams'>('overview');
  const [error, setError] = useState<string | null>(null);
  const hasTriggeredAnalysis = useRef(false);

  // Load project
  useEffect(() => {
    if (!id) return;
    
    let isMounted = true;

    const load = async () => {
      try {
        const p = await api.getProject(id);
        if (!isMounted) return;
        setProject(p);
        
        if (p.status === 'diagrams_ready') {
           api.getDiagrams(id).then(d => { if (isMounted) setDiagrams(d); }).catch(console.error);
        } else if (p.status === 'created' && !hasTriggeredAnalysis.current) {
          hasTriggeredAnalysis.current = true;
          try {
            const result = await api.analyzeProject(id);
            if (!isMounted) return;
            setProject(result);
            if (result.status === 'diagrams_ready') {
              api.getDiagrams(id).then(d => { if (isMounted) setDiagrams(d); }).catch(console.error);
            }
          } catch (err: any) {
            if (!isMounted) return;
            console.error("Analysis failed:", err);
            setError(err.message || 'Analysis failed');
          }
        }
      } catch (err: any) {
        if (!isMounted) return;
        setError(err.message || 'Failed to load project');
      }
    };

    load();

    return () => { isMounted = false; };
  }, [id]);

  if (error) {
    const isTruncated = error.includes('ANALYSIS_OUTPUT_TRUNCATED') || error.includes('AI response was too large');
    
    return (
      <div className="empty-state">
        <AlertTriangle className="empty-state-icon" style={{ color: 'var(--critical)' }} />
        <h2>{isTruncated ? 'Analysis Output Too Large' : 'Error Loading Project'}</h2>
        <p>{isTruncated 
          ? 'The AI response was too large and was truncated before completing the structured analysis. Please adjust the input or prompt to be more concise.' 
          : error}</p>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="empty-state">
        <div className="loading-spinner" style={{ width: 40, height: 40, marginBottom: '1rem' }} />
        <h2>Loading Project...</h2>
      </div>
    );
  }

  const isAnalyzing = project.status === 'created' || project.status === 'analyzing';
  const hasModel = !!project.structured_model;
  const model = project.structured_model;
  const gaps = project.gap_analysis;
  const arch = project.architecture;

  return (
    <div className="fade-in">
      <div className="section-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="section-title">{project.name}</h1>
          <div className="pipeline-steps">
            <span className={`pipeline-step ${project.status !== 'created' ? 'done' : 'active'}`}>
              <div className="pipeline-step-dot" /> Requirements
            </span>
            <span className="pipeline-arrow">→</span>
            <span className={`pipeline-step ${hasModel ? 'done' : (project.status === 'analyzing' ? 'active' : '')}`}>
              <div className="pipeline-step-dot" /> Model
            </span>
            <span className="pipeline-arrow">→</span>
            <span className={`pipeline-step ${gaps ? 'done' : (hasModel && !gaps ? 'active' : '')}`}>
              <div className="pipeline-step-dot" /> Gaps & Questions
            </span>
            <span className="pipeline-arrow">→</span>
            <span className={`pipeline-step ${arch ? 'done' : (gaps && !arch ? 'active' : '')}`}>
              <div className="pipeline-step-dot" /> Architecture
            </span>
            <span className="pipeline-arrow">→</span>
            <span className={`pipeline-step ${diagrams.length > 0 ? 'done' : (arch && diagrams.length === 0 ? 'active' : '')}`}>
              <div className="pipeline-step-dot" /> Diagrams
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.5rem' }}>
          <div className={`badge ${project.status === 'failed' ? 'badge-critical' : 'badge-inferred'}`}>
            {project.status.replace('_', ' ').toUpperCase()}
          </div>
          {project._debug_ai_requests && (
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', gap: '0.5rem', background: 'var(--bg-secondary)', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
              <span>Requests: <strong>{project._debug_ai_requests}</strong></span>
              <span>|</span>
              <span>Provider: <strong>{project._debug_provider}</strong></span>
            </div>
          )}
        </div>
      </div>

      {isAnalyzing && (
        <div className="card" style={{ textAlign: 'center', padding: '4rem 2rem' }}>
          <div className="loading-spinner" style={{ width: 40, height: 40, marginBottom: '1.5rem', borderWidth: '3px' }} />
          <h3>Analyzing Requirements</h3>
          <p style={{ maxWidth: '400px', margin: '0.5rem auto 1.5rem' }}>
            ArchLens is reading the raw notes, extracting requirements, and building the structured project model...
          </p>
          <div className="loading-bar" style={{ maxWidth: '300px', margin: '0 auto' }}>
            <div className="loading-bar-fill" />
          </div>
        </div>
      )}

      {project.status === 'failed' && (
        <div className="alert alert-error">
          <AlertTriangle size={24} style={{ flexShrink: 0 }} />
          <div>
            <strong>Analysis Failed</strong>
            <p>An error occurred while analyzing the project. Please check the backend logs.</p>
          </div>
        </div>
      )}

      {model && (
        <>
          <div className="tabs">
            <button className={`tab ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
              <Server size={16} /> Overview
            </button>
            <button className={`tab ${activeTab === 'requirements' ? 'active' : ''}`} onClick={() => setActiveTab('requirements')}>
              <List size={16} /> Requirements ({model.functional_requirements.length})
            </button>
            <button className={`tab ${activeTab === 'questions' ? 'active' : ''}`} onClick={() => setActiveTab('questions')}>
              <HelpCircle size={16} /> Open Questions {gaps && `(${gaps.questions.length})`}
            </button>
            <button className={`tab ${activeTab === 'architecture' ? 'active' : ''}`} onClick={() => setActiveTab('architecture')}>
              <Layers size={16} /> Architecture
            </button>
            <button className={`tab ${activeTab === 'diagrams' ? 'active' : ''}`} onClick={() => setActiveTab('diagrams')}>
              <CheckCircle2 size={16} /> Diagrams ({diagrams.length})
            </button>
          </div>

          <div style={{ marginTop: '1.5rem' }}>
            
            {/* Overview Tab */}
            {activeTab === 'overview' && (
              <div className="grid-2 fade-in">
                <div className="card">
                  <h3 className="card-title" style={{ marginBottom: '1rem' }}>Project Summary</h3>
                  <p style={{ fontSize: '0.95rem', marginBottom: '1rem' }}>{model.summary}</p>
                  
                  <div style={{ display: 'flex', gap: '2rem', marginTop: '1.5rem' }}>
                    <div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Domain</div>
                      <div style={{ fontWeight: 500 }}>{model.domain}</div>
                    </div>
                    <div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Actors</div>
                      <div style={{ fontWeight: 500 }}>{model.actors.length}</div>
                    </div>
                  </div>
                </div>

                <div className="card">
                  <h3 className="card-title" style={{ marginBottom: '1rem' }}><Users size={16} className="text-accent" /> Actors</h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {model.actors.map(actor => (
                      <div key={actor.id} style={{ padding: '0.75rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                          <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{actor.name}</span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{actor.type}</span>
                        </div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{actor.description}</div>
                      </div>
                    ))}
                    {model.actors.length === 0 && <div className="text-muted text-sm">No actors identified.</div>}
                  </div>
                </div>

                {arch && (
                  <div className="card" style={{ gridColumn: '1 / -1' }}>
                    <h3 className="card-title" style={{ marginBottom: '1rem' }}><Layers size={16} className="text-accent" /> Proposed Architecture</h3>
                    <p style={{ fontSize: '0.95rem', marginBottom: '1.5rem' }}>{arch.summary}</p>
                    
                    <div className="grid-3">
                      {Object.entries(arch.technology_stack).map(([layer, tech]) => (
                        <div key={layer} style={{ padding: '1rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                          <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>{layer}</div>
                          <div style={{ fontWeight: 600 }}>{tech}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Requirements Tab */}
            {activeTab === 'requirements' && (
              <div className="fade-in">
                {model.functional_requirements.map(req => (
                  <div key={req.id} className="req-item">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div className="req-id">{req.id} <span style={{ color: 'var(--text-muted)', fontWeight: 'normal', marginLeft: '0.5rem' }}>{req.category}</span></div>
                      <span className={`badge badge-${req.status}`}>{req.status}</span>
                    </div>
                    <div className="req-description">{req.description}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Questions Tab */}
            {activeTab === 'questions' && (
              <div className="fade-in">
                {gaps ? (
                  <>
                    <div className="card" style={{ marginBottom: '1.5rem' }}>
                      <p style={{ margin: 0, fontSize: '0.95rem' }}>{gaps.coverage_summary}</p>
                    </div>
                    
                    {gaps.questions.map(q => (
                      <div key={q.id} className={`question-item ${q.priority}`}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                          <div className="badge" style={{ fontSize: '0.7rem', padding: '0.1rem 0.4rem', background: 'var(--bg-input)' }}>{q.category}</div>
                          <span className={`badge badge-${q.priority}`}>{q.priority}</span>
                        </div>
                        <div className="question-text">{q.question}</div>
                        <div className="question-reason">{q.why_it_matters}</div>
                      </div>
                    ))}
                  </>
                ) : (
                  <div className="empty-state">
                    <RefreshCw className="empty-state-icon" />
                    <h2>Analyzing Gaps...</h2>
                  </div>
                )}
              </div>
            )}

            {/* Architecture Tab */}
            {activeTab === 'architecture' && arch && (
              <div className="fade-in">
                <div className="grid-2">
                  <div className="card">
                    <h3 className="card-title" style={{ marginBottom: '1rem' }}><Layers size={16} /> Components</h3>
                    <ul style={{ paddingLeft: '1.2rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {arch.components.map(c => <li key={c.id}><strong>{c.name}</strong>: {c.responsibility}</li>)}
                    </ul>
                  </div>
                  
                  <div className="card">
                    <h3 className="card-title" style={{ marginBottom: '1rem' }}><AlertTriangle size={16} className="text-accent" /> System Assumptions</h3>
                    <ul style={{ paddingLeft: '1.2rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {arch.assumptions.map((a, i) => <li key={i}>{a}</li>)}
                    </ul>
                  </div>
                </div>

                <h3 className="section-title" style={{ marginTop: '2rem', marginBottom: '1rem' }}>Architectural Decisions (ADRs)</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  {arch.decisions.map(d => (
                    <div key={d.id} className="card">
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                        <h4 style={{ margin: 0, color: 'var(--accent-blue-light)' }}>{d.decision}</h4>
                      </div>
                      <p style={{ fontSize: '0.9rem', marginBottom: '0.75rem' }}>{d.reason}</p>
                      
                      {(d.alternative || d.tradeoff) && (
                        <div style={{ background: 'var(--bg-secondary)', padding: '0.75rem', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem' }}>
                          {d.alternative && <div style={{ marginBottom: '0.4rem' }}><strong style={{ color: 'var(--text-muted)' }}>Alternative:</strong> {d.alternative}</div>}
                          {d.tradeoff && <div><strong style={{ color: 'var(--text-muted)' }}>Tradeoff:</strong> {d.tradeoff}</div>}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Diagrams Tab */}
            {activeTab === 'diagrams' && (
              <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                {diagrams.length === 0 && (
                   <div className="empty-state">
                     <div className="loading-spinner" style={{ width: 30, height: 30, marginBottom: '1rem' }} />
                     <h2>Loading Diagrams...</h2>
                   </div>
                )}
                {diagrams.map(diagram => (
                  <div key={diagram.id} className="card" style={{ padding: '1rem' }}>
                    <DiagramEditor 
                      diagram={diagram} 
                      onUpdate={(updated) => {
                        setDiagrams(prev => prev.map(d => d.id === updated.id ? updated : d));
                      }} 
                    />
                  </div>
                ))}
              </div>
            )}
            
          </div>
        </>
      )}
    </div>
  );
}
