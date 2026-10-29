import React, { useEffect, useMemo, useState } from 'react'
import { MapContainer, TileLayer, Polyline, Marker, Popup, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import {
  DEFAULT_MAP_CENTER,
  DEFAULT_MAP_ZOOM,
  DEFAULT_TILE_URL,
  DEFAULT_TILE_ATTRIBUTION,
  parseRouteGeometry,
  getBoundsFromCoordinates,
  getRiskMeta,
  getRouteStyle,
  extractRouteCheckpoints,
  isValidCoordinate,
  RISK_LEVEL_META,
} from '../utils/mapUtils'

// Configure Leaflet default image fallback in bundlers
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconUrl: markerIcon,
  iconRetinaUrl: markerIcon2x,
  shadowUrl: markerShadow,
})

/**
 * Controller component that observes bounds changes and smoothly adjusts the map viewport.
 */
function MapBoundsController({ bounds }) {
  const map = useMap()

  useEffect(() => {
    if (bounds && Array.isArray(bounds) && bounds.length === 2) {
      try {
        map.fitBounds(bounds, {
          padding: [50, 50],
          maxZoom: 13,
          animate: true,
          duration: 0.75,
        })
      } catch {
        // Ignore fitBounds errors on unrendered or zero-dimension maps
      }
    }
  }, [map, bounds])

  return null
}

/**
 * Helper to build custom HTML DivIcons for Departure Origin, Final Destination, and Checkpoints.
 * Avoids broken PNG paths and provides accessible SVG/CSS styling with high contrast.
 */
function createEndpointIcon(type = 'origin', label = 'A') {
  const isOrigin = type === 'origin'
  const bgColor = isOrigin ? '#10b981' : '#ef4444' // Emerald for Origin, Red for Dest
  const borderColor = isOrigin ? '#065f46' : '#991b1b'

  const html = `
    <div class="custom-map-pin pin-${type}" style="
      background-color: ${bgColor};
      border: 2px solid ${borderColor};
      color: #ffffff;
      width: 28px;
      height: 28px;
      border-radius: 50% 50% 50% 0;
      transform: rotate(-45deg);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 4px 10px rgba(0,0,0,0.5);
      font-weight: 800;
      font-size: 13px;
    ">
      <span style="transform: rotate(45deg);">${label}</span>
    </div>
  `

  return L.divIcon({
    className: 'endpoint-div-icon',
    html,
    iconSize: [28, 28],
    iconAnchor: [14, 28],
    popupAnchor: [0, -28],
  })
}

function createCheckpointIcon(sequence, riskLevel = 'unknown') {
  const meta = getRiskMeta(riskLevel)
  const isSevereOrNoTravel = riskLevel === 'severe' || riskLevel === 'no_travel'

  const html = `
    <div class="custom-checkpoint-pin risk-${meta.key}" style="
      background-color: ${meta.color};
      border: 2px solid ${meta.borderColor};
      color: ${meta.textColor};
      width: ${isSevereOrNoTravel ? '26px' : '22px'};
      height: ${isSevereOrNoTravel ? '26px' : '22px'};
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.45);
      font-weight: 800;
      font-size: ${isSevereOrNoTravel ? '12px' : '10.5px'};
    " title="Checkpoint #${sequence} (${meta.label})">
      <span>${isSevereOrNoTravel ? '!' : sequence}</span>
    </div>
  `

  return L.divIcon({
    className: 'checkpoint-div-icon',
    html,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -14],
  })
}

export function InteractiveMap({
  routes = [],
  selectedRouteId = null,
  onSelectRoute,
  isLoading = false,
  error = null,
  isPendingSetup = false,
  hasSearched = false,
  queryParams = {},
}) {
  const [showLegend, setShowLegend] = useState(true)

  // Find currently selected route or default to first/recommended
  const activeRoute = useMemo(() => {
    if (!routes || routes.length === 0) return null
    if (selectedRouteId) {
      const match = routes.find((r) => r.route_id === selectedRouteId)
      if (match) return match
    }
    const recommended = routes.find((r) => r.recommendation?.is_recommended)
    return recommended || routes[0]
  }, [routes, selectedRouteId])

  // Extract geometries for all available routes
  const routeGeometries = useMemo(() => {
    return (routes || []).map((route, idx) => {
      const latLngs = parseRouteGeometry(route.geometry)
      const isSelected = activeRoute?.route_id === route.route_id
      const style = getRouteStyle(route, isSelected, idx)
      return {
        routeId: route.route_id,
        displayName: route.display_name,
        rank: route.rank || idx + 1,
        isRecommended: Boolean(route.recommendation?.is_recommended),
        latLngs,
        hasGeometry: latLngs.length >= 2,
        style,
        route,
      }
    })
  }, [routes, activeRoute])

  // Compute active bounds across all valid coordinates of the selected route (or all routes)
  const mapBounds = useMemo(() => {
    if (!activeRoute) return null

    // Prefer coordinates from selected route's geometry
    const activeGeo = routeGeometries.find((g) => g.routeId === activeRoute.route_id)
    if (activeGeo && activeGeo.hasGeometry) {
      return getBoundsFromCoordinates(activeGeo.latLngs)
    }

    // Fall back to checkpoint coordinates if geometry is absent
    const checkpoints = extractRouteCheckpoints(activeRoute)
    if (checkpoints.length >= 2) {
      const cpPoints = checkpoints.map((cp) => [cp.latitude, cp.longitude])
      return getBoundsFromCoordinates(cpPoints)
    }

    return null
  }, [activeRoute, routeGeometries])

  // Extract checkpoints for active route
  const activeCheckpoints = useMemo(() => {
    return extractRouteCheckpoints(activeRoute)
  }, [activeRoute])

  // Check if active route is missing geometry coordinates
  const activeHasMissingGeometry = useMemo(() => {
    if (!activeRoute) return false
    const match = routeGeometries.find((g) => g.routeId === activeRoute.route_id)
    return !match || !match.hasGeometry
  }, [activeRoute, routeGeometries])

  // Origin & Destination endpoints from checkpoints
  const originCheckpoint = activeCheckpoints.length > 0 ? activeCheckpoints[0] : null
  const destinationCheckpoint =
    activeCheckpoints.length > 1 ? activeCheckpoints[activeCheckpoints.length - 1] : null
  const intermediateCheckpoints =
    activeCheckpoints.length > 2 ? activeCheckpoints.slice(1, activeCheckpoints.length - 1) : []

  return (
    <div className="card map-card" role="region" aria-label="Interactive Route Map and Weather Hazard Overlay">
      {/* 1. Map Header & Route Selector Tabs */}
      <div className="map-card-header">
        <div className="map-header-left">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
            <line x1="8" y1="2" x2="8" y2="18" />
            <line x1="16" y1="6" x2="16" y2="22" />
          </svg>
          <span className="map-title">Route Geometry &amp; Weather Hazard Overlay</span>
        </div>

        {/* Route Selector Tab Bar (When routes are available) */}
        {routes.length > 0 && (
          <div className="map-route-selector-tabs" role="tablist" aria-label="Select Route Option">
            {routes.map((route, idx) => {
              const isSelected = activeRoute?.route_id === route.route_id
              const isRecommended = route.recommendation?.is_recommended
              return (
                <button
                  key={route.route_id}
                  role="tab"
                  aria-selected={isSelected}
                  className={`map-tab-btn ${isSelected ? 'active' : ''}`}
                  onClick={() => onSelectRoute && onSelectRoute(route.route_id)}
                >
                  <span className="tab-rank">#{route.rank || idx + 1}</span>
                  <span className="tab-name">{route.display_name}</span>
                  {isRecommended && <span className="tab-rec-star">★ Rec</span>}
                </button>
              )
            })}
          </div>
        )}

        {/* Header Right Actions */}
        <div className="map-badges">
          <button
            type="button"
            className="btn-legend-toggle"
            onClick={() => setShowLegend((prev) => !prev)}
            aria-expanded={showLegend}
            title="Toggle Weather Hazard Legend"
          >
            {showLegend ? 'Hide Legend' : 'Show Legend'}
          </button>
          <span className="badge badge-subtle">OpenStreetMap Tiles</span>
        </div>
      </div>

      {/* 2. Map Canvas Area */}
      <div className="map-viewport-wrapper">
        <MapContainer
          center={DEFAULT_MAP_CENTER}
          zoom={DEFAULT_MAP_ZOOM}
          scrollWheelZoom={true}
          className="leaflet-map-canvas"
          aria-label="Interactive route navigation map"
        >
          {/* Dynamic Viewport Controller */}
          {mapBounds && <MapBoundsController bounds={mapBounds} />}

          {/* OpenStreetMap Tile Layer (OSM Fair-Use Compliant) */}
          <TileLayer
            attribution={DEFAULT_TILE_ATTRIBUTION}
            url={DEFAULT_TILE_URL}
            maxZoom={19}
          />

          {/* Alternative Route Polylines (Rendered beneath selected route) */}
          {routeGeometries
            .filter((g) => g.hasGeometry && g.routeId !== activeRoute?.route_id)
            .map((geom, idx) => (
              <Polyline
                key={`alt-poly-${geom.routeId}-${idx}`}
                positions={geom.latLngs}
                pathOptions={geom.style}
                eventHandlers={{
                  click: () => onSelectRoute && onSelectRoute(geom.routeId),
                }}
              >
                <Tooltip sticky>
                  <strong>{geom.displayName}</strong> (Alternative #{geom.rank})
                  <br />
                  Click to select and view weather checkpoints
                </Tooltip>
              </Polyline>
            ))}

          {/* Selected Active Route Polyline */}
          {routeGeometries
            .filter((g) => g.hasGeometry && g.routeId === activeRoute?.route_id)
            .map((geom, idx) => (
              <Polyline
                key={`active-poly-${geom.routeId}-${idx}`}
                positions={geom.latLngs}
                pathOptions={geom.style}
              >
                <Tooltip sticky>
                  <strong>{geom.displayName}</strong> {geom.isRecommended ? '★ Recommended' : ''}
                  <br />
                  Distance: {geom.route?.distance_miles?.toFixed(1)} mi • Drive Time: {geom.route?.duration_formatted}
                </Tooltip>
              </Polyline>
            ))}

          {/* Origin Marker (Point A) */}
          {originCheckpoint && isValidCoordinate(originCheckpoint.latitude, originCheckpoint.longitude) && (
            <Marker
              position={[originCheckpoint.latitude, originCheckpoint.longitude]}
              icon={createEndpointIcon('origin', 'A')}
            >
              <Popup className="map-custom-popup">
                <div className="popup-content">
                  <div className="popup-badge badge-origin">Origin / Departure</div>
                  <h4 className="popup-title">{originCheckpoint.name || queryParams.origin || 'Origin'}</h4>
                  <p className="popup-meta">
                    <strong>Coordinates:</strong> {originCheckpoint.latitude.toFixed(4)}, {originCheckpoint.longitude.toFixed(4)}
                  </p>
                  {originCheckpoint.estimated_arrival && (
                    <p className="popup-meta">
                      <strong>Scheduled Departure:</strong> {new Date(originCheckpoint.estimated_arrival).toLocaleString()}
                    </p>
                  )}
                </div>
              </Popup>
            </Marker>
          )}

          {/* Destination Marker (Point B) */}
          {destinationCheckpoint && isValidCoordinate(destinationCheckpoint.latitude, destinationCheckpoint.longitude) && (
            <Marker
              position={[destinationCheckpoint.latitude, destinationCheckpoint.longitude]}
              icon={createEndpointIcon('destination', 'B')}
            >
              <Popup className="map-custom-popup">
                <div className="popup-content">
                  <div className="popup-badge badge-dest">Destination / Arrival</div>
                  <h4 className="popup-title">{destinationCheckpoint.name || queryParams.destination || 'Destination'}</h4>
                  <p className="popup-meta">
                    <strong>Coordinates:</strong> {destinationCheckpoint.latitude.toFixed(4)}, {destinationCheckpoint.longitude.toFixed(4)}
                  </p>
                  {destinationCheckpoint.estimated_arrival && (
                    <p className="popup-meta">
                      <strong>Est. Arrival:</strong> {new Date(destinationCheckpoint.estimated_arrival).toLocaleString()}
                    </p>
                  )}
                  {destinationCheckpoint.distance_from_origin_miles != null && (
                    <p className="popup-meta">
                      <strong>Total Distance:</strong> {destinationCheckpoint.distance_from_origin_miles.toFixed(1)} mi
                    </p>
                  )}
                </div>
              </Popup>
            </Marker>
          )}

          {/* Intermediate Checkpoint Risk Markers for Selected Route */}
          {intermediateCheckpoints.map((cp) => {
            const riskMeta = getRiskMeta(cp.risk_level)
            const weather = cp.weather
            return (
              <Marker
                key={`cp-${cp.sequence}-${cp.latitude}-${cp.longitude}`}
                position={[cp.latitude, cp.longitude]}
                icon={createCheckpointIcon(cp.sequence, cp.risk_level)}
              >
                <Popup className="map-custom-popup">
                  <div className="popup-content">
                    <div className="popup-header-row">
                      <span className="cp-seq-badge">#{cp.sequence}</span>
                      <span
                        className="popup-risk-badge"
                        style={{ backgroundColor: riskMeta.color, color: riskMeta.textColor }}
                      >
                        {riskMeta.icon} {riskMeta.label}
                      </span>
                    </div>

                    <h4 className="popup-title">{cp.name || `Waypoint #${cp.sequence}`}</h4>

                    <div className="popup-metrics-grid">
                      <div className="popup-metric">
                        <span className="p-label">Distance:</span>
                        <span className="p-val">{cp.distance_from_origin_miles != null ? `${cp.distance_from_origin_miles.toFixed(1)} mi` : 'N/A'}</span>
                      </div>
                      <div className="popup-metric">
                        <span className="p-label">Est. Arrival:</span>
                        <span className="p-val">
                          {cp.estimated_arrival ? new Date(cp.estimated_arrival).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'N/A'}
                        </span>
                      </div>
                      {weather?.temperature != null && (
                        <div className="popup-metric">
                          <span className="p-label">Temp:</span>
                          <span className="p-val">{Math.round(weather.temperature)}°F</span>
                        </div>
                      )}
                      {weather?.wind_speed_mph != null && (
                        <div className="popup-metric">
                          <span className="p-label">Wind:</span>
                          <span className="p-val">
                            {Math.round(weather.wind_speed_mph)} mph
                            {weather.wind_gust_mph ? ` (G ${Math.round(weather.wind_gust_mph)})` : ''}
                          </span>
                        </div>
                      )}
                      {weather?.precipitation_rate_in_per_hour > 0 && (
                        <div className="popup-metric">
                          <span className="p-label">Precip:</span>
                          <span className="p-val">{weather.precipitation_rate_in_per_hour.toFixed(2)} in/h</span>
                        </div>
                      )}
                      {weather?.snowfall_rate_in_per_hour > 0 && (
                        <div className="popup-metric">
                          <span className="p-label">Snow:</span>
                          <span className="p-val">{weather.snowfall_rate_in_per_hour.toFixed(2)} in/h</span>
                        </div>
                      )}
                    </div>

                    {cp.risk_summary && (
                      <div className="popup-risk-summary">
                        <strong>Hazard Factor:</strong> {cp.risk_summary}
                      </div>
                    )}
                  </div>
                </Popup>
              </Marker>
            )
          })}
        </MapContainer>

        {/* 3. Floating Overlay States */}

        {/* A. Initial State (Before user submission) */}
        {!hasSearched && !isLoading && (
          <div className="map-overlay-banner ready-overlay" role="status">
            <div className="overlay-content">
              <span className="overlay-icon">🗺️</span>
              <div>
                <strong>Interactive Map Ready</strong>
                <p>Enter dispatch origin, destination, schedule, and truck load weight to plot driving alternatives and weather risk checkpoints.</p>
              </div>
            </div>
          </div>
        )}

        {/* B. Loading State */}
        {isLoading && (
          <div className="map-overlay-banner loading-overlay" role="status" aria-live="polite">
            <div className="overlay-content">
              <span className="spinner-icon"></span>
              <div>
                <strong>Calculating Routes &amp; Forecasts...</strong>
                <p>Retrieving corridor geometry from Mapbox and checkpoint weather from Open-Meteo.</p>
              </div>
            </div>
          </div>
        )}

        {/* C. Provider Not Configured (HTTP 503) */}
        {isPendingSetup && !isLoading && (
          <div className="map-overlay-banner setup-overlay" role="alert">
            <div className="overlay-content">
              <span className="overlay-icon">⚙️</span>
              <div>
                <strong>Live Routing Setup Pending</strong>
                <p>Add <code>MAPBOX_ACCESS_TOKEN</code> to <code>backend/.env</code> to render real driving alternatives.</p>
              </div>
            </div>
          </div>
        )}

        {/* D. Missing Geometry Notice for Active Route */}
        {hasSearched && !isLoading && activeHasMissingGeometry && routes.length > 0 && (
          <div className="map-overlay-banner warning-overlay" role="note">
            <div className="overlay-content">
              <span className="overlay-icon">⚠️</span>
              <div>
                <strong>Route Geometry Unavailable</strong>
                <p>The backend returned route metrics, but polyline geometry was not included. Showing available coordinate checkpoints without connecting lines.</p>
              </div>
            </div>
          </div>
        )}

        {/* E. Error State */}
        {error && !isLoading && !isPendingSetup && (
          <div className="map-overlay-banner error-overlay" role="alert">
            <div className="overlay-content">
              <span className="overlay-icon">❌</span>
              <div>
                <strong>Map Rendering Paused</strong>
                <p>{error.message || 'Unable to retrieve routing data.'}</p>
              </div>
            </div>
          </div>
        )}

        {/* 4. Risk Level Legend Overlay */}
        {showLegend && (
          <div className="map-risk-legend-panel" role="region" aria-label="Weather Hazard Risk Legend">
            <div className="legend-header">
              <span className="legend-title">Weather Risk Thresholds</span>
              <button
                type="button"
                className="btn-legend-close"
                onClick={() => setShowLegend(false)}
                aria-label="Close Legend"
              >
                &times;
              </button>
            </div>
            <div className="legend-items">
              {Object.values(RISK_LEVEL_META).map((meta) => (
                <div key={meta.key} className="legend-row">
                  <span
                    className="legend-color-dot"
                    style={{ backgroundColor: meta.color, borderColor: meta.borderColor }}
                  ></span>
                  <div className="legend-text">
                    <span className="legend-label">{meta.label}</span>
                    <span className="legend-desc">{meta.description}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
