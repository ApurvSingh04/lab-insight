import React from 'react';
import SeverityBadge from './SeverityBadge';
import { ArrowRight, Loader } from 'lucide-react';

// ── Range Gauge ──────────────────────────────────────────────────────────────
const RangeGauge = ({ result, unit, minRef, maxRef }) => {
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
  const valPct = clamp(((val - scaleMin) / scaleRange) * 100);
  const isNormal = val >= minRef && val <= maxRef;

  return (
    <div className="range-gauge">
      <div className="gauge-track">
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
            {val} <span className="gauge-tooltip-unit">{unit}</span>
          </div>
          <div className="gauge-marker-dot" />
        </div>
      </div>
      <div className="gauge-labels">
        <span>{minRef} (min)</span>
        <span className="gauge-ref-label">
          Ref: {minRef}–{maxRef} {unit}
        </span>
        <span>{maxRef} (max)</span>
      </div>
    </div>
  );
};

// ── Result Card ───────────────────────────────────────────────────────────────
const ResultCard = ({ result, index }) => {
  const isPending = result.status === 'pending';
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
            <SeverityBadge severity={result.severity} />
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
        />
      )}
      {!isPending && result.reference_range && result.min_reference == null && (
        <div className="ref-range-text">
          Reference Range: <strong>{result.reference_range}</strong> {result.unit}
        </div>
      )}

      {/* ── Explanation ── */}
      <div className={`stack-explanation ${isPending ? 'skeleton' : ''}`}>
        {isPending ? (
          <div className="skeleton-lines">
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
      {!isPending && result.next_steps && (
        <div className="stack-next-steps">
          <ArrowRight size={15} />
          <span><strong>Next Steps:</strong> {result.next_steps}</span>
        </div>
      )}
    </div>
  );
};

// ── Results Display ───────────────────────────────────────────────────────────
const ResultsDisplay = ({ results }) => {
  if (!results || results.length === 0) return null;

  const done = results.filter(r => r.status === 'done').length;
  const total = results.length;

  const criticalCount = results.filter(r => r.severity === 'Critical').length;
  const warningCount = results.filter(r => r.severity === 'Warning').length;
  const normalCount = results.filter(r => r.severity === 'Normal').length;

  return (
    <div>
      {/* ── KPI Summary Counter Bar ── */}
      <div className="kpi-summary-bar">
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
      </div>

      {/* ── Progress Bar ── */}
      <div className="progress-bar-container">
        <div className="progress-bar-header">
          <span>
            {done === total
              ? '✅ Analysis complete!'
              : `⏳ Analyzing… (rate-limited to 5 req/min)`}
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
