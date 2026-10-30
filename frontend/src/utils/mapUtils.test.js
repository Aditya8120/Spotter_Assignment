import { test, describe } from 'node:test'
import assert from 'node:assert'
import {
  isValidCoordinate,
  parseRouteGeometry,
  getBoundsFromCoordinates,
  getRiskMeta,
  getRouteStyle,
  extractRouteCheckpoints,
  RISK_LEVEL_META,
  MAP_THEMES,
  DEFAULT_TILE_URL,
} from './mapUtils.js'

describe('mapUtils - isValidCoordinate', () => {
  test('validates standard latitudes and longitudes', () => {
    assert.strictEqual(isValidCoordinate(41.8781, -87.6298), true) // Chicago
    assert.strictEqual(isValidCoordinate(32.7767, -96.7970), true) // Dallas
    assert.strictEqual(isValidCoordinate(0, 0), true)
    assert.strictEqual(isValidCoordinate(-90, -180), true)
    assert.strictEqual(isValidCoordinate(90, 180), true)
  })

  test('rejects out of bounds coordinates', () => {
    assert.strictEqual(isValidCoordinate(90.1, 0), false)
    assert.strictEqual(isValidCoordinate(-90.1, 0), false)
    assert.strictEqual(isValidCoordinate(0, 180.1), false)
    assert.strictEqual(isValidCoordinate(0, -180.1), false)
  })

  test('rejects null, undefined, non-numbers, NaN, and Infinity', () => {
    assert.strictEqual(isValidCoordinate(null, -87.6), false)
    assert.strictEqual(isValidCoordinate(41.8, undefined), false)
    assert.strictEqual(isValidCoordinate('abc', 10), false)
    assert.strictEqual(isValidCoordinate(NaN, 10), false)
    assert.strictEqual(isValidCoordinate(Infinity, 10), false)
  })
})

describe('mapUtils - parseRouteGeometry', () => {
  test('correctly transforms GeoJSON [lon, lat] coordinates to Leaflet [lat, lon]', () => {
    const geojson = {
      type: 'LineString',
      coordinates: [
        [-87.6298, 41.8781], // Chicago [lon, lat]
        [-89.6501, 39.7817], // Springfield [lon, lat]
        [-90.1994, 38.6270], // St. Louis [lon, lat]
      ],
    }

    const leafletLatLngs = parseRouteGeometry(geojson)

    assert.strictEqual(leafletLatLngs.length, 3)
    assert.deepStrictEqual(leafletLatLngs[0], [41.8781, -87.6298])
    assert.deepStrictEqual(leafletLatLngs[1], [39.7817, -89.6501])
    assert.deepStrictEqual(leafletLatLngs[2], [38.627, -90.1994])
  })

  test('accepts raw array of coordinate pairs', () => {
    const raw = [
      [-104.9903, 39.7392],
      [-111.8910, 40.7608],
    ]
    const parsed = parseRouteGeometry(raw)
    assert.strictEqual(parsed.length, 2)
    assert.deepStrictEqual(parsed[0], [39.7392, -104.9903])
    assert.deepStrictEqual(parsed[1], [40.7608, -111.8910])
  })

  test('returns empty array when geometry is null, missing, or empty', () => {
    assert.deepStrictEqual(parseRouteGeometry(null), [])
    assert.deepStrictEqual(parseRouteGeometry(undefined), [])
    assert.deepStrictEqual(parseRouteGeometry({}), [])
    assert.deepStrictEqual(parseRouteGeometry({ coordinates: [] }), [])
    assert.deepStrictEqual(parseRouteGeometry({ coordinates: [[-87.6, 41.8]] }), []) // Single point is not a polyline
  })

  test('does not fabricate coordinates when geometry is absent', () => {
    const parsed = parseRouteGeometry({ coordinates: 'invalid-string' })
    assert.deepStrictEqual(parsed, [])
  })

  test('filters out corrupt coordinate tuples and preserves valid points', () => {
    const geojson = {
      type: 'LineString',
      coordinates: [
        [-87.6298, 41.8781],
        ['corrupt', null],
        [-999.0, 40.0], // Out of bounds lon
        [-90.1994, 38.6270],
      ],
    }
    const parsed = parseRouteGeometry(geojson)
    assert.strictEqual(parsed.length, 2)
    assert.deepStrictEqual(parsed[0], [41.8781, -87.6298])
    assert.deepStrictEqual(parsed[1], [38.6270, -90.1994])
  })
})

describe('mapUtils - getBoundsFromCoordinates', () => {
  test('computes bounding box [[minLat, minLon], [maxLat, maxLon]] correctly', () => {
    const points = [
      [41.8781, -87.6298], // Chicago
      [32.7767, -96.7970], // Dallas
      [38.6270, -90.1994], // St Louis
    ]

    const bounds = getBoundsFromCoordinates(points)

    assert.ok(bounds)
    assert.strictEqual(bounds[0][0], 32.7767) // minLat
    assert.strictEqual(bounds[0][1], -96.7970) // minLon
    assert.strictEqual(bounds[1][0], 41.8781) // maxLat
    assert.strictEqual(bounds[1][1], -87.6298) // maxLon
  })

  test('returns null for empty coordinate array or invalid entries', () => {
    assert.strictEqual(getBoundsFromCoordinates([]), null)
    assert.strictEqual(getBoundsFromCoordinates(null), null)
    assert.strictEqual(getBoundsFromCoordinates([['bad', 'data']]), null)
  })

  test('pads bounds when single coordinate point is provided', () => {
    const single = [[41.8781, -87.6298]]
    const bounds = getBoundsFromCoordinates(single)
    assert.ok(bounds)
    assert.ok(bounds[0][0] < 41.8781)
    assert.ok(bounds[1][0] > 41.8781)
  })
})

describe('mapUtils - getRiskMeta', () => {
  test('returns correct metadata for each standard risk level', () => {
    assert.strictEqual(getRiskMeta('low').key, 'low')
    assert.strictEqual(getRiskMeta('moderate').key, 'moderate')
    assert.strictEqual(getRiskMeta('high').key, 'high')
    assert.strictEqual(getRiskMeta('severe').key, 'severe')
    assert.strictEqual(getRiskMeta('no_travel').key, 'no_travel')
    assert.strictEqual(getRiskMeta('No-Travel').key, 'no_travel')
  })

  test('CRITICAL: never treats missing, null, or undefined risk as low - strictly maps to unknown', () => {
    assert.strictEqual(getRiskMeta(null).key, 'unknown')
    assert.strictEqual(getRiskMeta(undefined).key, 'unknown')
    assert.strictEqual(getRiskMeta('').key, 'unknown')
    assert.strictEqual(getRiskMeta('unrecognized_value').key, 'unknown')
    assert.strictEqual(getRiskMeta(123).key, 'unknown')
  })

  test('contains complete visual properties for each level', () => {
    Object.values(RISK_LEVEL_META).forEach((meta) => {
      assert.ok(meta.key)
      assert.ok(meta.label)
      assert.ok(meta.color)
      assert.ok(meta.icon)
      assert.ok(meta.description)
    })
  })
})

describe('mapUtils - getRouteStyle', () => {
  test('returns thick prominent stroke for selected route', () => {
    const style = getRouteStyle({ recommendation: { is_recommended: true } }, true, 0)
    assert.strictEqual(style.weight, 6)
    assert.strictEqual(style.opacity, 0.95)
    assert.strictEqual(style.dashArray, null)
  })

  test('returns dashed subtle stroke for alternative unselected routes', () => {
    const style = getRouteStyle({ recommendation: { is_recommended: false } }, false, 1)
    assert.strictEqual(style.weight, 4)
    assert.strictEqual(style.opacity, 0.55)
    assert.ok(style.dashArray)
  })
})

describe('mapUtils - extractRouteCheckpoints', () => {
  test('extracts valid checkpoints and sorts by sequence order', () => {
    const mockRoute = {
      checkpoints: [
        { sequence: 3, latitude: 38.627, longitude: -90.199, name: 'CP3' },
        { sequence: 1, latitude: 41.878, longitude: -87.629, name: 'CP1' },
        { sequence: 2, latitude: null, longitude: -88.0, name: 'Invalid' }, // Missing lat
        { sequence: 2, latitude: 40.0, longitude: -89.0, name: 'CP2' },
      ],
    }

    const checkpoints = extractRouteCheckpoints(mockRoute)

    assert.strictEqual(checkpoints.length, 3)
    assert.strictEqual(checkpoints[0].sequence, 1)
    assert.strictEqual(checkpoints[1].sequence, 2)
    assert.strictEqual(checkpoints[2].sequence, 3)
  })

  test('returns empty array when route has no checkpoints', () => {
    assert.deepStrictEqual(extractRouteCheckpoints(null), [])
    assert.deepStrictEqual(extractRouteCheckpoints({}), [])
    assert.deepStrictEqual(extractRouteCheckpoints({ checkpoints: [] }), [])
  })
})

describe('mapUtils - MAP_THEMES Light/Dark Mode', () => {
  test('provides free public tile configurations for both dark and light modes', () => {
    assert.ok(MAP_THEMES.dark)
    assert.ok(MAP_THEMES.light)

    // Dark theme properties (Keyless public OpenStreetMap tiles + CSS dark filter)
    assert.strictEqual(MAP_THEMES.dark.id, 'dark')
    assert.strictEqual(MAP_THEMES.dark.icon, '🌙')
    assert.ok(MAP_THEMES.dark.tileUrl.includes('tile.openstreetmap.org'))
    assert.ok(MAP_THEMES.dark.attribution.includes('OpenStreetMap'))
    assert.strictEqual(MAP_THEMES.dark.useCssDarkFilter, true)

    // Light theme properties
    assert.strictEqual(MAP_THEMES.light.id, 'light')
    assert.strictEqual(MAP_THEMES.light.icon, '☀️')
    assert.ok(MAP_THEMES.light.tileUrl.includes('tile.openstreetmap.org'))
    assert.ok(MAP_THEMES.light.attribution.includes('OpenStreetMap'))
    assert.strictEqual(MAP_THEMES.light.useCssDarkFilter, false)
  })

  test('DEFAULT_TILE_URL is defined and non-empty', () => {
    assert.ok(DEFAULT_TILE_URL)
    assert.strictEqual(typeof DEFAULT_TILE_URL, 'string')
  })
})
