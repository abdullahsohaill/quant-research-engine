/**
 * Header — Application header with branding
 */

export default function Header() {
  return (
    <header className="header">
      <div className="header-content">
        <div className="header-brand">
          <div className="header-logo">Q</div>
          <div>
            <div className="header-title">Quant Research Engine</div>
            <div className="header-subtitle">AI-Powered Financial Analysis</div>
          </div>
        </div>
        <div className="header-meta">
          <span className="header-badge">● Live</span>
        </div>
      </div>
    </header>
  );
}
