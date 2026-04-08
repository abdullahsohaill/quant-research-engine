/**
 * LoadingState — Animated loading indicator with status steps
 */

interface LoadingStateProps {
  query: string;
  statusMessages: string[];
}

export default function LoadingState({ query, statusMessages }: LoadingStateProps) {
  const steps = [
    { label: 'Validating input', icon: '🛡️' },
    { label: 'Fetching stock data via MCP', icon: '📡' },
    { label: 'Running SQL analytics', icon: '🔍' },
    { label: 'Computing financial ratios', icon: '📐' },
    { label: 'Generating investment memo', icon: '📝' },
    { label: 'Running critic review', icon: '🔎' },
  ];

  return (
    <div className="loading-container">
      <div className="loading-spinner" />
      <div className="loading-status">
        <strong>Analyzing:</strong> {query}
      </div>

      <div className="loading-steps">
        {steps.map((step, i) => (
          <div
            key={step.label}
            className={`loading-step ${
              i < statusMessages.length ? 'complete' : ''
            } ${i === statusMessages.length ? 'active' : ''}`}
            style={{ animationDelay: `${i * 0.1}s` }}
          >
            <span className="loading-step-icon">
              {i < statusMessages.length ? '✅' : i === statusMessages.length ? '⏳' : '○'}
            </span>
            <span>{step.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
