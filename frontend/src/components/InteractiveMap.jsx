import React, { useEffect, useMemo, useState } from 'react'
import { MapContainer, TileLayer, Polyline, Marker, Popup, Tooltip, Circle, useMap } from 'react-leaflet'
import L from 'leaflet'
import {
  DEFAULT_MAP_CENTER,
  DEFAULT_MAP_ZOOM,
  DEFAULT_TILE_URL,
  DEFAULT_TILE_ATTRIBUTION,
  parseRouteGeometry,
  getBoundsFromCoordinates,
  getRouteStyle,
  extractRouteCheckpoints,
  isValidCoordinate,
} from '../utils/mapUtils'
import {
  WEATHER_LAYERS,
  LAYER_COLOR_SCALES,
  generateForecastTimeline,
  getCheckpointLayerValue,
  matchCheckpointWeatherForTimestamp,
} from '../utils/weatherLayers'
import { WeatherLayerSelector } from './WeatherLayerSelector'
import { ForecastTimelineSlider } from './ForecastTimelineSlider'

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
 * Helper to build custom HTML DivIcons for Departure Origin and Final Destination endpoints.
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

/**
 * Creates dynamic checkpoint markers whose badge reflects the active weather layer's color.
 */
function createWeatherCheckpointIcon(sequence, layerMeta, layerKey) {
  const isSevereOrNoTravel = layerMeta.category === 'severe' || layerMeta.category === 'no_travel'
  const isUnknown = layerMeta.category === 'unknown'

  let glyph = sequence
  if (isSevereOrNoTravel) {
    glyph = '!'
  } else if (isUnknown) {
    glyph = '?'
  }

  const html = `
    <div class="custom-checkpoint-pin layer-${layerKey} cat-${layerMeta.category}" style="
      background-color: ${layerMeta.color};
      border: 2px solid ${layerMeta.color === '#64748b' ? '#334155' : '#ffffff'};
      color: #ffffff;
      width: ${isSevereOrNoTravel ? '26px' : '22px'};
      height: ${isSevereOrNoTravel ? '26px' : '22px'};
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 2px 8px rgba(0,0,0,0.45);
      font-weight: 800;
      font-size: ${isSevereOrNoTravel ? '12px' : '10.5px'};
    " title="Checkpoint #${sequence} (${layerMeta.label})">
      <span>${glyph}</span>
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
  const [activeWeatherLayer, setActiveWeatherLayer] = useState('risk')
  const [selectedHourOffset, setSelectedHourOffset] = useState(0)

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

  // Compute active bounds across all valid coordinates of the selected route
  const mapBounds = useMemo(() => {
    if (!activeRoute) return null

    const activeGeo = routeGeometries.find((g) => g.routeId === activeRoute.route_id)
    if (activeGeo && activeGeo.hasGeometry) {
      return getBoundsFromCoordinates(activeGeo.latLngs)
    }

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

  // Generate 0–48h forecast timeline slots relative to departure datetime
  const timelineSlots = useMemo(() => {
    const baseDt = queryParams?.departureDatetime || activeCheckpoints[0]?.estimated_arrival
    return generateForecastTimeline(baseDt, 48)
  }, [queryParams?.departureDatetime, activeCheckpoints])

  const activeSlot = timelineSlots[selectedHourOffset] || timelineSlots[0]

  // Check data availability for the currently selected hour across checkpoints
  const { isSlotAvailable, availabilityMessage } = useMemo(() => {
    if (!activeCheckpoints || activeCheckpoints.length === 0) {
      return { isSlotAvailable: false, availabilityMessage: 'No route checkpoints available.' }
    }

    if (!activeSlot?.isoTimestamp) {
      return { isSlotAvailable: false, availabilityMessage: 'Invalid timeline slot.' }
    }

    // Check if at least one checkpoint has valid forecast data for this timestamp
    const availableCount = activeCheckpoints.filter((cp) => {
      const match = matchCheckpointWeatherForTimestamp(cp, activeSlot.isoTimestamp)
      return match.isAvailable
    }).length

    if (availableCount > 0) {
      return {
        isSlotAvailable: true,
        availabilityMessage: `${availableCount} of ${activeCheckpoints.length} checkpoints have forecast data for this hour.`,
      }
    }

    const firstArrival = activeCheckpoints[0]?.estimated_arrival
    const arrivalText = firstArrival ? new Date(firstArrival).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'departure time'
    return {
      isSlotAvailable: false,
      availabilityMessage: `Forecast observation not recorded for ${activeSlot.label}. Route checkpoints have weather sampled at arrival (${arrivalText}).`,
    }
  }, [activeCheckpoints, activeSlot])

  // Endpoints
  const originCheckpoint = activeCheckpoints.length > 0 ? activeCheckpoints[0] : null
  const destinationCheckpoint =
    activeCheckpoints.length > 1 ? activeCheckpoints[activeCheckpoints.length - 1] : null
  const intermediateCheckpoints =
    activeCheckpoints.length > 2 ? activeCheckpoints.slice(1, activeCheckpoints.length - 1) : []

  // Dynamic color scale for active weather layer
  const currentScale = LAYER_COLOR_SCALES[activeWeatherLayer] || LAYER_COLOR_SCALES.risk
  const activeLayerMeta = WEATHER_LAYERS[activeWeatherLayer] || WEATHER_LAYERS.risk

  return (
    <div className="card map-card" role="region" aria-label="Interactive Route Map and Weather Hazard Heatmap">
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

        {/* Route Selector Tab Bar */}
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

      {/* 2. Weather Layer Selector Bar */}
      <WeatherLayerSelector
        activeLayer={activeWeatherLayer}
        onSelectLayer={setActiveWeatherLayer}
      />

      {/* 3. Forecast Timeline Slider (0–48 Hours) */}
      <ForecastTimelineSlider
        slots={timelineSlots}
        selectedHour={selectedHourOffset}
        onSelectHour={setSelectedHourOffset}
        isSlotAvailable={isSlotAvailable}
        availabilityMessage={availabilityMessage}
      />

      {/* 4. Map Canvas Area */}
      <div className="map-viewport-wrapper">
        <MapContainer
          center={DEFAULT_MAP_CENTER}
          zoom={DEFAULT_MAP_ZOOM}
          scrollWheelZoom={true}
          className="leaflet-map-canvas"
          aria-label="Interactive route navigation and weather heatmap map"
        >
          {/* Dynamic Viewport Controller */}
          {mapBounds && <MapBoundsController bounds={mapBounds} />}

          {/* OpenStreetMap Tile Layer */}
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
                  Click to select corridor and inspect weather
                </Tooltip>
              </Polyline>
            ))}

          {/* Selected Active Route Polyline */}
          {routeGeometries
            .filter((g) => g.hasGeometry && g.routeId === activeRoute?.route_id)
            .map((geom, idx) => (
              <React.Fragment key={`active-group-${geom.routeId}-${idx}`}>
                {/* Glow heatmap layer underlay following the corridor */}
                <Polyline
                  positions={geom.latLngs}
                  pathOptions={{
                    color: isSlotAvailable ? '#3b82f6' : '#64748b',
                    weight: 12,
                    opacity: 0.3,
                    lineCap: 'round',
                    lineJoin: 'round',
                  }}
                />
                {/* Sharp polyline stroke on top */}
                <Polyline
                  positions={geom.latLngs}
                  pathOptions={geom.style}
                >
                  <Tooltip sticky>
                    <strong>{geom.displayName}</strong> {geom.isRecommended ? '★ Recommended' : ''}
                    <br />
                    Distance: {geom.route?.distance_miles?.toFixed(1)} mi • Drive Time: {geom.route?.duration_formatted}
                    <br />
                    Layer: <strong>{activeLayerMeta.label}</strong> at {activeSlot.label}
                  </Tooltip>
                </Polyline>
              </React.Fragment>
            ))}

          {/* Heatmap Influence Halos around each checkpoint */}
          {activeCheckpoints.map((cp) => {
            const layerVal = getCheckpointLayerValue(
              cp,
              activeWeatherLayer,
              activeSlot.isoTimestamp,
              queryParams?.loadWeightLb
            )
            return (
              <Circle
                key={`halo-${cp.sequence}-${cp.latitude}-${cp.longitude}`}
                center={[cp.latitude, cp.longitude]}
                radius={32000} // ~20 miles radius representing sampled segment influence
                pathOptions={{
                  fillColor: layerVal.color,
                  fillOpacity: layerVal.isAvailable ? 0.28 : 0.08,
                  color: layerVal.color,
                  weight: 1,
                  opacity: layerVal.isAvailable ? 0.6 : 0.2,
                }}
              />
            )
          })}

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

          {/* Intermediate Checkpoints styled according to active weather layer */}
          {intermediateCheckpoints.map((cp) => {
            const layerVal = getCheckpointLayerValue(
              cp,
              activeWeatherLayer,
              activeSlot.isoTimestamp,
              queryParams?.loadWeightLb
            )
            const weather = cp.weather
            return (
              <Marker
                key={`cp-${cp.sequence}-${cp.latitude}-${cp.longitude}-${activeWeatherLayer}-${selectedHourOffset}`}
                position={[cp.latitude, cp.longitude]}
                icon={createWeatherCheckpointIcon(cp.sequence, layerVal, activeWeatherLayer)}
              >
                <Popup className="map-custom-popup">
                  <div className="popup-content">
                    <div className="popup-header-row">
                      <span className="cp-seq-badge">#{cp.sequence}</span>
                      <span
                        className="popup-risk-badge"
                        style={{ backgroundColor: layerVal.color, color: '#ffffff' }}
                      >
                        {layerVal.label}
                      </span>
                    </div>

                    <h4 className="popup-title">{cp.name || `Waypoint #${cp.sequence}`}</h4>

                    {/* Active Layer Readout */}
                    <div className="popup-layer-highlight" style={{ borderColor: layerVal.color }}>
                      <span className="highlight-label">{activeLayerMeta.label}:</span>
                      <strong className="highlight-val">{layerVal.displayValue}</strong>
                    </div>

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

                    {layerVal.reason && (
                      <div className="popup-layer-notice">
                        <span>ℹ️ {layerVal.reason}</span>
                      </div>
                    )}
                  </div>
                </Popup>
              </Marker>
            )
          })}
        </MapContainer>

        {/* 5. Honest Approximation Watermark / Notice */}
        {routes.length > 0 && (
          <div className="map-approximation-badge" title="Data Integrity Notice">
            <span className="approx-dot"></span>
            <span>Corridor Heatmap Approximation (Sampled Checkpoints; Not Radar Reflectivity)</span>
          </div>
        )}

        {/* 6. Floating Overlay States */}

        {/* A. Initial Ready State */}
        {!hasSearched && !isLoading && (
          <div className="map-overlay-banner ready-overlay" role="status">
            <div className="overlay-content">
              <span className="overlay-icon">🗺️</span>
              <div>
                <strong>Interactive Weather Map Ready</strong>
                <p>Enter dispatch parameters to calculate route options, inspect multi-hazard weather overlays, and scrub 0–48h forecasts.</p>
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
                <p>Add <code>MAPBOX_ACCESS_TOKEN</code> to <code>backend/.env</code> to render real driving alternatives and weather overlays.</p>
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
                <p>The backend returned route metrics, but polyline geometry was not included. Showing checkpoint weather markers without connecting lines.</p>
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

        {/* 7. Dynamic Weather Layer Legend Panel */}
        {showLegend && (
          <div className="map-risk-legend-panel" role="region" aria-label={`Weather Hazard Legend: ${activeLayerMeta.label}`}>
            <div className="legend-header">
              <div className="legend-title-group">
                <span className="legend-title">{activeLayerMeta.icon} {activeLayerMeta.label}</span>
                <span className="legend-unit-tag">{activeLayerMeta.unit}</span>
              </div>
              <button
                type="button"
                className="btn-legend-close"
                onClick={() => setShowLegend(false)}
                aria-label="Close Legend"
              >
                &times;
              </button>
            </div>
            <p className="legend-layer-desc">{activeLayerMeta.description}</p>
            <div className="legend-items">
              {Object.entries(currentScale).map(([catKey, meta]) => (
                <div key={catKey} className="legend-row">
                  <span
                    className="legend-color-dot"
                    style={{ backgroundColor: meta.color, borderColor: meta.color }}
                  ></span>
                  <div className="legend-text">
                    <span className="legend-label">{meta.label}</span>
                    <span className="legend-desc">{meta.threshold}</span>
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
