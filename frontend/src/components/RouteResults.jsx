import React, { useState } from 'react'
import { RouteCard } from './RouteCard'

export function RouteResults({
  routes = [],
  recommendationSummary = null,
  isLoading = false,
  error = null,
  isPendingSetup = false,
  pendingSetupMessage = '',
  hasSearched = false,
  queryParams = null,
}) {
  const [selectedRouteId, setSelectedRouteId] = useState(routes[0]?.route_id || null)

  // 1. Loading State
  if (isLoading) {
    return (
      <div className="card results-status-card loading-state">
        <div className="status-spinner"></div>
        <h3 className="status-title">Calculating Weather-Aware Routes...</h3>
        <p className="status-description">
          Requesting driving routes from Mapbox Directions API, sampling checkpoints along each corridor,
          fetching hourly weather forecasts from Open-Meteo, and calculating load-specific risk scores.
        </p>
        <div className="loading-steps">
          <span className="step-badge">1. Geocoding Corridor</span>
          <span className="step-badge">2. Generating Mapbox Vectors</span>
          <span className="step-badge">3. Open-Meteo Forecasts</span>
          <span className="step-badge">4. Lexicographic Ranking</span>
        </div>
      </div>
    )
  }

  // 2. Pending Setup State (HTTP 503 provider_not_configured)
  if (isPendingSetup) {
    return (
      <div className="card results-status-card setup-pending-state" role="alert">
        <div className="status-icon-circle setup-icon">
          <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          </svg>
        </div>
        <div className="setup-badge-row">
          <span className="badge badge-setup-pending">Live Setup Required</span>
          <span className="badge badge-subtle">HTTP 503 Provider Unconfigured</span>
        </div>
        <h3 className="status-title">Mapbox Routing Provider Not Configured</h3>
        <p className="status-description">
          {pendingSetupMessage ||
            'The backend route calculation service is ready, but requires a valid Mapbox access token to fetch real-world driving geometries and coordinates.'}
        </p>
        <div className="setup-instructions-box">
          <h4 className="instructions-title">Quick Configuration Steps:</h4>
          <ol className="instructions-list">
            <li>Obtain a free public token from your <a href="https://account.mapbox.com/" target="_blank" rel="noopener noreferrer">Mapbox Account Dashboard</a> (starts with <code>pk.</code>).</li>
            <li>Add it to the backend environment file: <code>backend/.env</code> &rarr; <code>MAPBOX_ACCESS_TOKEN=pk.your_token</code>.</li>
            <li>Restart the Django backend server: <code>python manage.py runserver</code>.</li>
          </ol>
        </div>
      </div>
    )
  }

  // 3. Error State (Network error, HTTP 400 validation, HTTP 500, etc.)
  if (error) {
    const isNetwork = error.status === 0 || error.code === 'network_error'
    const isValidation = error.status === 400

    return (
      <div className="card results-status-card error-state" role="alert">
        <div className="status-icon-circle error-icon">
          <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <div className="setup-badge-row">
          <span className="badge badge-error">{isNetwork ? 'Network Connection Error' : isValidation ? 'Validation Error (HTTP 400)' : `Server Error (${error.status || '500'})`}</span>
        </div>
        <h3 className="status-title">{isNetwork ? 'Cannot Connect to Backend Server' : 'Route Planning Request Failed'}</h3>
        <p className="status-description">{error.message}</p>

        {isNetwork && (
          <div className="error-troubleshoot-box">
            <strong>Troubleshooting:</strong>
            <p>Ensure the Django development server is running on port 8000:</p>
            <code>cd backend &amp;&amp; source .venv/bin/activate &amp;&amp; python manage.py runserver</code>
          </div>
        )}

        {isValidation && error.fieldErrors && Object.keys(error.fieldErrors).length > 0 && (
          <div className="error-troubleshoot-box">
            <strong>Field Errors:</strong>
            <ul>
              {Object.entries(error.fieldErrors).map(([field, msg]) => (
                <li key={field}><strong>{field}:</strong> {msg}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    )
  }

  // 4. Initial Empty State (Before user has submitted form)
  if (!hasSearched) {
    return (
      <div className="card results-empty-state">
        <div className="empty-icon-circle">
          <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" strokeWidth="1.75">
            <circle cx="12" cy="12" r="10" />
            <polygon points="12 8 8 12 12 16 12 8" />
            <line x1="16" y1="12" x2="12" y2="12" />
          </svg>
        </div>
        <h3 className="empty-title">Ready to Plan Commercial Route</h3>
        <p className="empty-description">
          Enter shipment origin, destination, departure schedule, and truck load weight in the dispatch form,
          then click <strong>"Find Routes &amp; Analyze Weather"</strong> to retrieve driving alternatives
          and multi-hazard weather risk evaluations from the backend API.
        </p>
        <div className="empty-guidelines">
          <div className="guideline-badge">
            <span className="dot"></span>
            <span>Real-time Mapbox alternatives</span>
          </div>
          <div className="guideline-badge">
            <span className="dot"></span>
            <span>Open-Meteo hourly weather at checkpoint arrival</span>
          </div>
          <div className="guideline-badge">
            <span className="dot"></span>
            <span>Load-specific wind &amp; blizzard rules</span>
          </div>
          <div className="guideline-badge">
            <span className="dot"></span>
            <span>Lexicographic safety ranking</span>
          </div>
        </div>
      </div>
    )
  }

  // 5. Successful Results State
  if (routes.length === 0) {
    return (
      <div className="card results-status-card" role="region">
        <h3 className="status-title">No Routes Available</h3>
        <p className="status-description">
          The routing provider could not find driving routes between <strong>{queryParams?.origin}</strong> and <strong>{queryParams?.destination}</strong>.
          Please verify that both locations are accessible by commercial road transport.
        </p>
      </div>
    )
  }

  return (
    <section className="results-section" aria-labelledby="results-heading">
      {/* Executive Summary Banner */}
      {recommendationSummary && (
        <div className={`recommendation-summary-card ${recommendationSummary.all_routes_unsafe ? 'all-unsafe' : 'has-recommendation'}`}>
          <div className="summary-header">
            <div className="summary-title-row">
              <span className="summary-icon">{recommendationSummary.all_routes_unsafe ? '⚠️' : '🛡️'}</span>
              <h2 id="results-heading" className="summary-heading">
                {recommendationSummary.all_routes_unsafe
                  ? 'NO SAFE ROUTE AVAILABLE — ALL OPTIONS ENCOUNTER NO TRAVEL ADVISORIES'
                  : 'Dispatch Recommendation & Safety Rationale'}
              </h2>
            </div>
            <span className="badge badge-success">
              {recommendationSummary.total_options_evaluated} Option{recommendationSummary.total_options_evaluated !== 1 ? 's' : ''} Evaluated
            </span>
          </div>

          <p className="summary-narrative">{recommendationSummary.executive_summary}</p>

          <div className="summary-policies">
            <div className="policy-item">
              <span className="policy-label">Lexicographic Hierarchy:</span>
              <div className="policy-pills">
                {recommendationSummary.ranking_priority?.map((p, idx) => (
                  <span key={idx} className="hint-pill">{p}</span>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Corridor Header */}
      <div className="results-header-bar">
        <div>
          <h3 className="results-heading">
            Candidate Driving Routes ({routes.length} Available)
          </h3>
          <p className="results-subheading">
            Corridor: <strong>{queryParams?.origin}</strong> &rarr; <strong>{queryParams?.destination}</strong> &bull; Truck Weight: <strong>{queryParams?.loadWeightLb?.toLocaleString()} lb</strong>
          </p>
        </div>
      </div>

      {/* Route Cards Grid */}
      <div className="route-cards-grid">
        {routes.map((route) => (
          <RouteCard
            key={route.route_id}
            route={route}
            isSelected={selectedRouteId === route.route_id}
            onSelect={() => setSelectedRouteId(route.route_id)}
          />
        ))}
      </div>
    </section>
  )
}
