/**
 * AnalysisReport — Renders the investment memo and critique
 */

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { AnalyzeResponse } from '../types';

interface AnalysisReportProps {
  response: AnalyzeResponse;
  query: string;
  onNewAnalysis: () => void;
}

export default function AnalysisReport({
  response,
  query,
  onNewAnalysis,
}: AnalysisReportProps) {
  const [showCritique, setShowCritique] = useState(false);

  if (!response.success || !response.report) {
    return (
      <div className="error-container animate-fade-in">
        <div className="error-card">
          <div className="error-icon">⚠️</div>
          <p className="error-message">
            {response.error || 'Analysis failed. Please try again.'}
          </p>
          <button className="retry-button" onClick={onNewAnalysis}>
            Try Again
          </button>
        </div>
      </div>
    );
  }

  const metadata = response.metadata;

  return (
    <div className="report-container animate-fade-in-up">
      {/* Report Header */}
      <div className="report-header">
        <div className="report-title">
          <span>📊</span>
          Analysis: {query}
        </div>
        <div className="report-meta">
          {metadata?.elapsed_seconds && (
            <span className="report-meta-item">
              ⏱️ {metadata.elapsed_seconds}s
            </span>
          )}
          {metadata?.iterations && (
            <span className="report-meta-item">
              🔄 {metadata.iterations} steps
            </span>
          )}
          {metadata?.tool_calls && (
            <span className="report-meta-item">
              🔧 {metadata.tool_calls.length} tool calls
            </span>
          )}
          <button className="retry-button" onClick={onNewAnalysis}>
            New Analysis
          </button>
        </div>
      </div>

      {/* Warnings */}
      {response.warnings.length > 0 && (
        <div style={{ marginBottom: 'var(--space-md)' }}>
          {response.warnings.map((w, i) => (
            <div
              key={i}
              style={{
                padding: '8px 12px',
                background: 'rgba(245, 158, 11, 0.1)',
                border: '1px solid rgba(245, 158, 11, 0.2)',
                borderRadius: 'var(--radius-md)',
                color: 'var(--color-warning)',
                fontSize: '0.85rem',
                marginBottom: '4px',
              }}
            >
              ⚠️ {w}
            </div>
          ))}
        </div>
      )}

      {/* Main Report */}
      <div className="report-card">
        <div className="markdown-content">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {response.report}
          </ReactMarkdown>
        </div>
      </div>

      {/* Tool Calls Summary */}
      {metadata?.tool_calls && metadata.tool_calls.length > 0 && (
        <div className="report-card" style={{ marginTop: 'var(--space-md)' }}>
          <h3 style={{ marginBottom: 'var(--space-md)', fontSize: '0.95rem', fontWeight: 600 }}>
            🔧 Tool Execution Log
          </h3>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem' }}>
            {metadata.tool_calls.map((tc, i) => (
              <div
                key={i}
                style={{
                  padding: '6px 10px',
                  borderBottom: '1px solid var(--border-default)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  color: tc.status === 'success' ? 'var(--color-success)' : 'var(--color-error)',
                }}
              >
                <span>
                  {tc.status === 'success' ? '✅' : '❌'}{' '}
                  <span style={{ color: 'var(--text-accent)' }}>{tc.tool}</span>
                  ({JSON.stringify(tc.args).slice(0, 60)}...)
                </span>
                <span style={{ color: 'var(--text-muted)' }}>
                  Step {tc.iteration}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Critic Review */}
      {response.critique && (
        <div className="critique-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="critique-header">
              <span>🔎</span> Quality Review (Critic Agent)
            </div>
            <button
              className="critique-toggle"
              onClick={() => setShowCritique(!showCritique)}
            >
              {showCritique ? 'Hide' : 'Show'} Review
            </button>
          </div>

          {showCritique && (
            <div className="markdown-content" style={{ marginTop: 'var(--space-md)' }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {response.critique}
              </ReactMarkdown>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
