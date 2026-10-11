import { useState } from 'react';
import { api } from '../services/api';
import type { Diagram } from '../services/api';
import { MermaidRenderer } from './MermaidRenderer';
import { Edit2, RefreshCw, AlertCircle, CheckCircle2 } from 'lucide-react';

interface DiagramEditorProps {
  diagram: Diagram;
  onUpdate: (diagram: Diagram) => void;
}

export function DiagramEditor({ diagram, onUpdate }: DiagramEditorProps) {
  const [source, setSource] = useState(diagram.mermaid_source);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isRepairing, setIsRepairing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasChanges = source !== diagram.mermaid_source;

  const handleSave = async () => {
    if (!hasChanges) return;
    setIsSaving(true);
    setError(null);
    try {
      const updated = await api.updateDiagramSource(diagram.project_id, diagram.id, source);
      onUpdate(updated);
      setIsEditing(false);
    } catch (err: any) {
      setError(err.message || 'Failed to save diagram');
    } finally {
      setIsSaving(false);
    }
  };

  const handleRepair = async () => {
    setIsRepairing(true);
    setError(null);
    try {
      const repaired = await api.repairDiagram(diagram.project_id, diagram.id);
      onUpdate(repaired);
      setSource(repaired.mermaid_source);
    } catch (err: any) {
      setError(err.message || 'Failed to repair diagram');
    } finally {
      setIsRepairing(false);
    }
  };

  return (
    <div className="diagram-editor-container" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      
      {/* Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <h3 className="section-title" style={{ margin: 0 }}>{diagram.title}</h3>
          {!diagram.is_valid && (
            <span className="badge badge-critical" title="Syntax Error">
              <AlertCircle size={14} /> Invalid
            </span>
          )}
          {diagram.is_valid && (
            <span className="badge badge-explicit" title="Valid Syntax">
              <CheckCircle2 size={14} /> Valid
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {!diagram.is_valid && (
            <button 
              className="btn btn-secondary btn-sm" 
              onClick={handleRepair}
              disabled={isRepairing || isSaving}
            >
              {isRepairing ? <span className="loading-spinner" style={{ width: 14, height: 14 }} /> : <RefreshCw size={14} />}
              Auto-Repair
            </button>
          )}
          <button 
            className={`btn btn-sm ${isEditing ? (hasChanges ? 'btn-primary' : 'btn-secondary') : 'btn-secondary'}`}
            onClick={() => {
              if (isEditing && hasChanges) {
                handleSave();
              } else {
                setIsEditing(!isEditing);
                if (isEditing) setSource(diagram.mermaid_source); // cancel edit
              }
            }}
            disabled={isSaving || isRepairing}
          >
            {isSaving ? (
              <span className="loading-spinner" style={{ width: 14, height: 14 }} />
            ) : isEditing ? (
              hasChanges ? 'Save Changes' : 'Close Editor'
            ) : (
              <><Edit2 size={14} /> Edit Source</>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          <AlertCircle size={18} style={{ marginTop: '2px' }} />
          <div>{error}</div>
        </div>
      )}

      {/* Editor & Render Split View */}
      <div className={isEditing ? "diagram-editor" : ""}>
        {isEditing && (
          <div className="diagram-source-pane">
            <div className="pane-header">
              <span>Mermaid Source</span>
              <span style={{ fontSize: '0.7rem', fontWeight: 'normal', color: 'var(--text-muted)' }}>
                v{diagram.version}
              </span>
            </div>
            <textarea
              className="diagram-source-textarea"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              spellCheck={false}
            />
          </div>
        )}
        <div className={`diagram-render-pane ${!isEditing ? 'dark-bg' : ''}`} style={{ minHeight: '400px' }}>
          <MermaidRenderer source={source} onError={() => {}} />
        </div>
      </div>

      {/* Validation Errors */}
      {diagram.validation_errors && diagram.validation_errors.length > 0 && !isEditing && (
        <div className="alert alert-warning" style={{ marginTop: '1rem' }}>
          <AlertCircle size={18} style={{ marginTop: '2px', flexShrink: 0 }} />
          <div>
            <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Syntax Issues Detected:</div>
            <ul style={{ paddingLeft: '1.2rem', margin: 0, fontSize: '0.8rem' }}>
              {diagram.validation_errors.map((err, i) => (
                <li key={i}>{err}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}
