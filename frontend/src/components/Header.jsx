import React from 'react'

export function Header({ onReset, isDemoMode = false, onToggleDemo }) {
  return (
    <header className="app-header">
      <div className="header-brand">
        <div className="brand-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="1" y="3" width="15" height="13" rx="2" />
            <polygon points="16 8 20 8 23 11 23 16 16 16 8" />
            <circle cx="5.5" cy="18.5" r="2.5" />
            <circle cx="18.5" cy="18.5" r="2.5" />
          </svg>
        </div>
        <div>
          <h1 className="brand-title">Weather-Aware Truck Routing</h1>
          <p className="brand-subtitle">Commercial Fleet Dispatch &amp; Weather Hazard Risk Assessment</p>
        </div>
      </div>

      <div className="header-meta">
        <div className="status-badge live" title="Connected to Django REST backend">
          <span className="status-dot"></span>
          <span>Backend: DRF API Ready</span>
        </div>
        {isDemoMode ? (
          <div className="status-badge demo" title="Demonstration mode: Viewing simulated corridors and mock weather forecasts">
            <span className="status-dot demo"></span>
            <span>Mode: Demo (Simulated Data)</span>
          </div>
        ) : (
          <div className="status-badge live" title="Live mode: Dispatches requests to backend endpoint">
            <span className="status-dot"></span>
            <span>Mode: Live Dispatch</span>
          </div>
        )}
        {onToggleDemo && (
          <button
            type="button"
            className={`btn-secondary btn-sm ${isDemoMode ? 'btn-demo-active' : ''}`}
            onClick={onToggleDemo}
            title={isDemoMode ? 'Exit demo mode and return to live dispatch' : 'Load demonstration corridors with simulated weather'}
          >
            {isDemoMode ? 'Exit Demo' : 'Demo Corridor'}
          </button>
        )}
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

