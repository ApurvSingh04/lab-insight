import React from 'react';
import SeverityBadge from './SeverityBadge';
import { ArrowRight, Loader, User } from 'lucide-react';

// ── Range Gauge ──────────────────────────────────────────────────────────────
const RangeGauge = ({ result, unit, minRef, maxRef, origMinRef, origMaxRef, rangeSource }) => {
  const val = parseFloat(result);
  if (isNaN(val) || minRef == null || maxRef == null) return null;

  // Build a scale from 0 to 100 where [minRef, maxRef] = [25%, 75%]
  const range = maxRef - minRef;
  const padding = range * 0.5; // 50% padding on each side for context
  const scaleMin = minRef - padding;
  const scaleMax = maxRef + padding;
  const scaleRange = scaleMax - scaleMin;

  const clamp = (v) => Math.max(0, Math.min(100, v));
  const refStartPct = clamp(((minRef - scaleMin) / scaleRange) * 100);
  const refWidthPct = clamp(((maxRef - minRef) / scaleRange) * 100);
  
  let origStartPct = null;
  let origWidthPct = null;
  if (origMinRef != null && origMaxRef != null) {
    origStartPct = clamp(((origMinRef - scaleMin) / scaleRange) * 100);
    origWidthPct = clamp(((origMaxRef - origMinRef) / scaleRange) * 100);
  }

  const valPct = clamp(((val - scaleMin) / scaleRange) * 100);
  const isNormal = val >= minRef && val <= maxRef;

  let deviationText = "Normal";
  if (val > maxRef && maxRef !== 0) {
    deviationText = `+${(((val - maxRef) / maxRef) * 100).toFixed(1)}%`;
  } else if (val < minRef && minRef !== 0) {
    deviationText = `-${(((minRef - val) / minRef) * 100).toFixed(1)}%`;
  }

  return (
    <div className="range-gauge">
      <div className="gauge-track">
        {/* Original Standard zone outline (if adjusted) */}
        {origStartPct != null && origWidthPct != null && (
          <div
            className="gauge-original-zone"
            style={{ 
              left: `${origStartPct}%`, width: `${origWidthPct}%`,
              position: 'absolute', top: 0, height: '100%',
              border: '2px dashed rgba(255,255,255,0.3)',
              boxSizing: 'border-box', borderRadius: '4px'
            }}
          />
        )}
        {/* Normal zone highlight */}
        <div
          className="gauge-normal-zone"
          style={{ left: `${refStartPct}%`, width: `${refWidthPct}%` }}
        />
        {/* Value marker */}
        <div
          className={`gauge-marker ${isNormal ? 'marker-normal' : 'marker-abnormal'}`}
          style={{ left: `${valPct}%` }}
        >
          <div className="gauge-tooltip">
            {deviationText}
          </div>
          <div className="gauge-marker-dot" />
        </div>
      </div>
      <div className="gauge-labels">
        <span>{scaleMin.toFixed(1)} (min)</span>
        <span className="gauge-ref-label">
          {rangeSource === 'patient_adjusted' ? 'Adjusted Ref: ' : 'Ref: '} {minRef}–{maxRef} {unit}
        </span>
        <span>{scaleMax.toFixed(1)} (max)</span>
      </div>
    </div>
  );
};

// ── Result Card ───────────────────────────────────────────────────────────────
const ResultCard = ({ result, index }) => {
  const isPending = result.status === 'pending';
  const isProcessingLLM = result.status === 'processing_llm';
  const isError = result.status === 'error';

  return (
    <div
      className={`result-card-stack severity-${isPending ? 'pending' : result.severity}`}
      style={{ animationDelay: `${index * 0.07}s` }}
    >
      {/* ── Header row ── */}
      <div className="stack-header">
        <div className="stack-title-group">
          {isPending ? (
            <div className="badge badge-pending">
              <Loader size={12} className="spin-icon" /> Analyzing
            </div>
          ) : (
            <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
                <SeverityBadge severity={result.severity} />
                {result.urgency && result.urgency !== "..." && (
                   <span className={`badge badge-urgency-${result.urgency.toLowerCase()}`}>{result.urgency}</span>
                )}
                {result.routing_specialty && result.routing_specialty !== "..." && (
                   <span className="badge badge-specialty">{result.routing_specialty}</span>
                )}
                {isProcessingLLM && <Loader size={12} className="spin-icon" style={{ color: 'var(--text-secondary)' }} />}
                {result.original_severity && result.original_severity !== result.severity && (
                  <span style={{ fontSize: '0.8rem', color: 'var(--warning-text)', fontStyle: 'italic', marginLeft: '4px' }}>
                    (was {result.original_severity})
                  </span>
                )}
            </div>
          )}
          <h3 className="stack-test-name">{result.test_name}</h3>
        </div>
        <div className="stack-value-group">
          <span className="stack-value">{result.result}</span>
          <span className="stack-unit">{result.unit}</span>
        </div>
      </div>

      {/* ── Range Gauge ── */}
      {!isPending && result.min_reference != null && result.max_reference != null && (
        <RangeGauge
          result={result.result}
          unit={result.unit}
          minRef={result.min_reference}
          maxRef={result.max_reference}
          origMinRef={result.original_min}
          origMaxRef={result.original_max}
          rangeSource={result.range_source}
        />
      )}
      {!isPending && result.reference_range && result.min_reference == null && (
        <div className="ref-range-text">
          Reference Range: <strong>{result.reference_range}</strong> {result.unit}
        </div>
      )}
      {!isPending && result.range_source === 'patient_adjusted' && (
        <div style={{ fontSize: '0.8rem', color: 'var(--warning-text)', padding: '4px 12px', background: 'var(--warning-bg)', borderRadius: '4px', marginTop: '8px', display: 'inline-block' }}>
          Adjusted for patient context
        </div>
      )}

      {/* ── Explanation ── */}
      <div className={`stack-explanation ${isPending || isProcessingLLM ? 'skeleton' : ''}`}>
        {isPending || isProcessingLLM ? (
          <div className="skeleton-lines">
            {isProcessingLLM && <span style={{fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '8px', display: 'block'}}>AI is typing explanation...</span>}
            <div className="skeleton-line" style={{ width: '92%' }} />
            <div className="skeleton-line" style={{ width: '78%' }} />
            <div className="skeleton-line" style={{ width: '55%' }} />
          </div>
        ) : isError ? (
          <span style={{ color: 'var(--critical-text)' }}>{result.explanation}</span>
        ) : (
          <>
            <span className="explanation-label">Clinical Explanation</span>
            <p>{result.explanation}</p>
          </>
        )}
      </div>

      {/* ── Next Steps ── */}
      {!(isPending || isProcessingLLM) && result.next_steps && (
        <div className="stack-next-steps">
          <ArrowRight size={15} />
          <span><strong>Next Steps:</strong> {result.next_steps}</span>
        </div>
      )}
    </div>
  );
};

// ── Results Display ───────────────────────────────────────────────────────────
const ResultsDisplay = ({ results, patientContext, onClear }) => {
  if (!results || results.length === 0) return null;

  const done = results.filter(r => r.status === 'done').length;
  const total = results.length;

  const criticalCount = results.filter(r => r.severity === 'Critical').length;
  const warningCount = results.filter(r => r.severity === 'Warning').length;
  const normalCount = results.filter(r => r.severity === 'Normal').length;

  return (
    <div>
      {/* ── KPI Summary Counter Bar ── */}
      <div className="kpi-summary-bar" style={{ position: 'relative' }}>
        <div className="kpi-card kpi-total">
          <span className="kpi-count">{total}</span>
          <span className="kpi-label">Total Tests</span>
        </div>
        <div className="kpi-card kpi-critical">
          <span className="kpi-count">{criticalCount}</span>
          <span className="kpi-label">Critical</span>
        </div>
        <div className="kpi-card kpi-warning">
          <span className="kpi-count">{warningCount}</span>
          <span className="kpi-label">Warning</span>
        </div>
        <div className="kpi-card kpi-normal">
          <span className="kpi-count">{normalCount}</span>
          <span className="kpi-label">Normal</span>
        </div>
        
        <button 
          onClick={onClear}
          style={{
            position: 'absolute',
            right: 0,
            top: '-35px',
            background: 'transparent',
            border: '1px solid var(--panel-border)',
            color: 'var(--text-secondary)',
            padding: '4px 12px',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '0.85rem'
          }}
        >
          Clear Results
        </button>
      </div>

      {patientContext && (
        <div style={{ 
          margin: '0 auto 2rem auto', 
          padding: '12px 16px', 
          background: 'rgba(30, 41, 59, 0.5)', 
          border: '1px solid var(--panel-border)', 
          borderRadius: '8px', 
          maxWidth: '800px',
          color: 'var(--text-primary)',
          fontSize: '0.9rem',
          display: 'flex',
          gap: '8px',
          alignItems: 'flex-start'
        }}>
          <span style={{ fontSize: '1.2rem' }}><User size={18} /></span>
          <div>
            <strong style={{ display: 'block', marginBottom: '4px', color: 'var(--text-secondary)' }}>Global Patient Context:</strong>
            {patientContext}
          </div>
        </div>
      )}

      {/* ── Progress Bar ── */}
      <div className="progress-bar-container">
        <div className="progress-bar-header">
          <span>
            {done === total
              ? 'Analysis complete!'
              : `Analyzing… (rate-limited to 5 req/min)`}
          </span>
          <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
            {done} / {total}
          </span>
        </div>
        <div className="progress-bar-track">
          <div className="progress-bar-fill" style={{ width: `${(done / total) * 100}%` }} />
        </div>
      </div>

      {/* ── Results Stack ── */}
      <div className="results-stack">
        {results.map((result, index) => (
          <ResultCard key={result.id} result={result} index={index} />
        ))}
      </div>
    </div>
  );
};

export default ResultsDisplay;
