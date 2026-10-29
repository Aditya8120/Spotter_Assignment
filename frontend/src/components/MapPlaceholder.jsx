import React from 'react'

export function MapPlaceholder({ plannedOrigin, plannedDestination, isPlanned }) {
  return (
    <div className="card map-card">
      <div className="map-card-header">
        <div className="map-header-left">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
            <line x1="8" y1="2" x2="8" y2="18" />
            <line x1="16" y1="6" x2="16" y2="22" />
          </svg>
          <span className="map-title">Route Geometry &amp; Weather Hazard Overlay</span>
        </div>
        <div className="map-badges">
          <span className="badge badge-map-pending">Mapbox Integration: Step 9</span>
          <span className="badge badge-subtle">Placeholder View</span>
        </div>
      </div>

      <div className="map-canvas-placeholder" role="region" aria-label="Interactive Map Preview Area">
        {/* Subtle grid lines background overlay */}
        <div className="map-grid-overlay" aria-hidden="true"></div>

        {/* Mock coordinate crosshairs */}
        <div className="map-crosshair top-left" aria-hidden="true">
          <span>41°52'N 87°37'W</span>
        </div>
        <div className="map-crosshair bottom-right" aria-hidden="true">
          <span>32°46'N 96°48'W</span>
        </div>

        {/* Compass rose */}
        <div className="map-compass" aria-hidden="true" title="Compass Orientation">
          <span className="compass-n">N</span>
          <div className="compass-needle"></div>
        </div>

        {/* Map Center Content */}
        <div className="map-center-content">
          <div className="map-icon-halo">
            <svg viewBox="0 0 24 24" width="44" height="44" fill="none" stroke="currentColor" strokeWidth="1.75">
              <polygon points="3 11 22 2 13 21 11 13 3 11" />
            </svg>
          </div>

          <h3 className="map-placeholder-heading">Interactive Map Visualization Canvas</h3>

          <p className="map-placeholder-body">
            Full Mapbox GL JS vector rendering, dynamic route polylines, weather hazard heatmaps,
            and checkpoint inspection popups will be connected in <strong>Step 9</strong>.
          </p>

          {isPlanned && (
            <div className="map-planned-corridor">
              <span className="corridor-label">Planned Dispatch Corridor:</span>
              <span className="corridor-route">
                <strong>{plannedOrigin}</strong> &rarr; <strong>{plannedDestination}</strong>
              </span>
            </div>
          )}

          <div className="map-feature-pills">
            <span className="pill">🛣️ Mapbox Driving Alternatives</span>
            <span className="pill">🌦️ Open-Meteo Radar Overlays</span>
            <span className="pill">🔴 Hazard Color-Coded Segments</span>
            <span className="pill">📍 Checkpoint Popups</span>
          </div>
        </div>
      </div>
    </div>
  )
}
