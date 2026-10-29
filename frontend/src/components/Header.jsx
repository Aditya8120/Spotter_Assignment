import React from 'react'

export function Header({ onReset }) {
  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="1" y="3" width="15" height="13" rx="2" />
            <polygon points="16 8 20 8 23 11 23 16 16 16 16 8" />
            <circle cx="5.5" cy="18.5" r="2.5" />
            <circle cx="18.5" cy="18.5" r="2.5" />
          </svg>
        </div>
        <div>
          <h1 className="brand-title">Weather-Aware Truck Routing</h1>
          <p className="brand-subtitle">Commercial Fleet Dispatch & Weather Hazard Risk Assessment</p>
        </div>
      </div>

      <div className="header-meta">
        <div className="status-badge live" title="Steps 1–7 implemented in backend">
          <span className="status-dot"></span>
          <span>Backend: API Engine Ready</span>
        </div>
        <div className="status-badge demo" title="UI mockup mode - map and live API connect in Step 9">
          <span className="status-dot demo"></span>
          <span>Frontend: Step 8 UI Mode</span>
        </div>
        {onReset && (
          <button
            type="button"
            className="btn-secondary btn-sm"
            onClick={onReset}
            title="Reset form to defaults"
          >
            Reset Form
          </button>
        )}
      </div>
    </header>
  )
}
