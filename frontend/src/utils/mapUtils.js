/**
 * Utilities for route geometry processing, coordinate transformation,
 * risk-level styling, Leaflet marker creation, and bounds calculation.
 */

// Free public tile configurations for Light and Dark modes (100% Free Tier, No API key required)
export const MAP_THEMES = {
  dark: {
    id: 'dark',
    name: 'Dark Map',
    icon: '🌙',
    tileUrl:
      (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_MAP_TILE_URL_DARK) ||
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    badgeLabel:
      (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_MAP_TILE_URL_DARK)
        ? 'Custom Dark Tiles'
        : 'OpenStreetMap Dark (Keyless Free Tier)',
    useCssDarkFilter: !(typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_MAP_TILE_URL_DARK),
  },
  light: {
    id: 'light',
    name: 'Light Map',
    icon: '☀️',
    tileUrl:
      (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_MAP_TILE_URL_LIGHT) ||
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    badgeLabel: 'OpenStreetMap Light (Keyless Free Tier)',
    useCssDarkFilter: false,
  },
}

// Default OpenStreetMap tile layer and attribution for backwards-compatibility
export const DEFAULT_TILE_URL = MAP_THEMES.dark.tileUrl
export const DEFAULT_TILE_ATTRIBUTION = MAP_THEMES.dark.attribution

// Default center (Geographic center of Contiguous United States) and zoom level
export const DEFAULT_MAP_CENTER = [39.8283, -98.5795]
export const DEFAULT_MAP_ZOOM = 4

/**
 * Validates whether a latitude and longitude pair is a valid real-world coordinate.
 * Latitude must be within [-90, 90], Longitude must be within [-180, 180].
 */
export function isValidCoordinate(lat, lon) {
  if (lat === null || lat === undefined || lon === null || lon === undefined) {
    return false
  }
  const nLat = Number(lat)
  const nLon = Number(lon)
  if (!Number.isFinite(nLat) || !Number.isFinite(nLon)) {
    return false
  }
  return nLat >= -90.0 && nLat <= 90.0 && nLon >= -180.0 && nLon <= 180.0
}

/**
 * Parses GeoJSON LineString coordinates [lon, lat] from the backend API into Leaflet [lat, lon] tuples.
 *
 * GeoJSON standard uses [longitude, latitude].
 * Leaflet requires [latitude, longitude].
 *
 * Rejects invalid, non-numeric, or out-of-bounds coordinates.
 * Returns an empty array if geometry is missing or contains fewer than 2 valid points.
 * NEVER fabricates intermediate points or creates artificial lines.
 */
export function parseRouteGeometry(geometry) {
  if (!geometry || typeof geometry !== 'object') {
    return []
  }

  // Handle GeoJSON LineString: { type: "LineString", coordinates: [[lon, lat], ...] }
  let rawCoords = null
  if (Array.isArray(geometry.coordinates)) {
    rawCoords = geometry.coordinates
  } else if (Array.isArray(geometry)) {
    rawCoords = geometry
  }

  if (!rawCoords || rawCoords.length < 2) {
    return []
  }

  const validLatLngs = []
  for (const point of rawCoords) {
    if (Array.isArray(point) && point.length >= 2) {
      const lon = point[0]
      const lat = point[1]
      if (isValidCoordinate(lat, lon)) {
        validLatLngs.push([Number(lat), Number(lon)])
      }
    }
  }

  return validLatLngs.length >= 2 ? validLatLngs : []
}

/**
 * Calculates Leaflet-compatible bounding box [[minLat, minLon], [maxLat, maxLon]]
 * from a list of [lat, lon] points. Returns null if coordinates list is empty or invalid.
 */
export function getBoundsFromCoordinates(latLngs) {
  if (!Array.isArray(latLngs) || latLngs.length === 0) {
    return null
  }

  let minLat = Infinity
  let maxLat = -Infinity
  let minLon = Infinity
  let maxLon = -Infinity
  let validCount = 0

  for (const point of latLngs) {
    if (Array.isArray(point) && point.length >= 2) {
      const [lat, lon] = point
      if (isValidCoordinate(lat, lon)) {
        if (lat < minLat) minLat = lat
        if (lat > maxLat) maxLat = lat
        if (lon < minLon) minLon = lon
        if (lon > maxLon) maxLon = lon
        validCount++
      }
    }
  }

  if (validCount === 0) {
    return null
  }

  // If all points are identical (single location), add a slight delta to avoid zero-dimension bounds
  if (minLat === maxLat && minLon === maxLon) {
    const delta = 0.05
    return [
      [minLat - delta, minLon - delta],
      [maxLat + delta, maxLon + delta],
    ]
  }

  return [
    [minLat, minLon],
    [maxLat, maxLon],
  ]
}

/**
 * Metadata and color tokens for weather hazard risk levels.
 *
 * CRITICAL RULE: Never treat missing or null risk data as 'low'.
 * If risk level is missing, null, or unrecognized, it maps strictly to 'unknown'.
 */
export const RISK_LEVEL_META = {
  low: {
    key: 'low',
    label: 'Low Risk',
    color: '#10b981', // Emerald green
    textColor: '#ffffff',
    bgBadge: '#064e3b',
    borderColor: '#059669',
    icon: '🟢',
    description: 'Wind <25 mph, precip <0.10 in/h, snow <1.0 in/h',
  },
  moderate: {
    key: 'moderate',
    label: 'Moderate Risk',
    color: '#f59e0b', // Amber
    textColor: '#1e293b',
    bgBadge: '#78350f',
    borderColor: '#d97706',
    icon: '🟡',
    description: 'Wind 25–34 mph, precip 0.10–0.25 in/h, snow 1.0–1.9 in/h',
  },
  high: {
    key: 'high',
    label: 'High Risk',
    color: '#f97316', // Orange
    textColor: '#ffffff',
    bgBadge: '#7c2d12',
    borderColor: '#ea580c',
    icon: '🟠',
    description: 'Wind 35–44 mph, precip >0.25–0.50 in/h, snow 2.0–2.9 in/h',
  },
  severe: {
    key: 'severe',
    label: 'Severe Risk',
    color: '#ef4444', // Red
    textColor: '#ffffff',
    bgBadge: '#7f1d1d',
    borderColor: '#dc2626',
    icon: '🔴',
    description: 'Wind 45–54 mph, precip >0.50 in/h, snow ≥3.0 in/h',
  },
  no_travel: {
    key: 'no_travel',
    label: 'No Travel Advisory',
    color: '#991b1b', // Deep Crimson
    textColor: '#ffffff',
    bgBadge: '#450a0a',
    borderColor: '#b91c1c',
    icon: '⛔',
    description: 'Wind ≥55 mph, or elevated crosswind threshold for light/empty truck',
  },
  unknown: {
    key: 'unknown',
    label: 'Unknown / Pending',
    color: '#64748b', // Slate Gray
    textColor: '#ffffff',
    bgBadge: '#1e293b',
    borderColor: '#475569',
    icon: '⚪',
    description: 'Weather data unavailable or pending assessment',
  },
}

/**
 * Normalizes any risk string into a valid risk level key.
 * Any missing or unrecognized value is strictly mapped to 'unknown'.
 */
export function getRiskMeta(riskLevel) {
  if (!riskLevel || typeof riskLevel !== 'string') {
    return RISK_LEVEL_META.unknown
  }
  const normalized = riskLevel.trim().toLowerCase().replace(/[\s-]+/g, '_')
  return RISK_LEVEL_META[normalized] || RISK_LEVEL_META.unknown
}

/**
 * Returns accessible styling configuration for route polylines.
 * Selected route is drawn with thick, prominent strokes.
 * Alternative routes are drawn with distinct, subtle colors and dashed lines.
 */
export function getRouteStyle(route, isSelected, index = 0) {
  const isRecommended = route?.recommendation?.is_recommended

  if (isSelected) {
    return {
      color: isRecommended ? '#2563eb' : '#3b82f6', // Bright primary blue
      weight: 6,
      opacity: 0.95,
      dashArray: null,
      lineCap: 'round',
      lineJoin: 'round',
      pane: 'overlayPane',
    }
  }

  // Non-selected alternative routes (muted, distinct palette)
  const altPalette = [
    { color: '#8b5cf6', dashArray: '6, 8' }, // Purple
    { color: '#06b6d4', dashArray: '4, 6' }, // Cyan
    { color: '#64748b', dashArray: '5, 7' }, // Slate
  ]
  const choice = altPalette[index % altPalette.length]

  return {
    color: choice.color,
    weight: 4,
    opacity: 0.55,
    dashArray: choice.dashArray,
    lineCap: 'round',
    lineJoin: 'round',
    pane: 'overlayPane',
  }
}

/**
 * Extracts and filters valid checkpoints from a route in sequence order.
 * Ignores invalid coordinates and preserves original sequence numbering.
 */
export function extractRouteCheckpoints(route) {
  if (!route || !Array.isArray(route.checkpoints)) {
    return []
  }

  return route.checkpoints
    .filter((cp) => cp && isValidCoordinate(cp.latitude, cp.longitude))
    .sort((a, b) => (a.sequence || 0) - (b.sequence || 0))
}
