import { test, describe } from 'node:test'
import assert from 'node:assert'
import {
  parseRouteGeometry,
  getBoundsFromCoordinates,
  getRiskMeta,
  getRouteStyle,
  extractRouteCheckpoints,
  RISK_LEVEL_META,
} from './mapUtils.js'

describe('Map Integration & Scenarios - Route Selection', () => {
  const mockRoutes = [
    {
      route_id: 'route_primary',
      display_name: 'Primary via I-55 S',
      rank: 1,
      recommendation: { is_recommended: true, status: 'recommended' },
      geometry: {
        type: 'LineString',
        coordinates: [
          [-87.6298, 41.8781], // Chicago
          [-89.6501, 39.7817], // Springfield
          [-90.1994, 38.6270], // St. Louis
        ],
      },
      checkpoints: [
        { sequence: 1, latitude: 41.8781, longitude: -87.6298, name: 'Departure: Chicago', risk_level: 'low' },
        { sequence: 2, latitude: 39.7817, longitude: -89.6501, name: 'Waypoint 2', risk_level: 'moderate' },
        { sequence: 3, latitude: 38.6270, longitude: -90.1994, name: 'Arrival: St. Louis', risk_level: 'low' },
      ],
    },
    {
      route_id: 'route_alt_1',
      display_name: 'Alternative via I-57 S',
      rank: 2,
      recommendation: { is_recommended: false, status: 'viable_alternative' },
      geometry: {
        type: 'LineString',
        coordinates: [
          [-87.6298, 41.8781],
          [-88.2434, 40.1164], // Champaign
          [-90.1994, 38.6270],
        ],
      },
      checkpoints: [
        { sequence: 1, latitude: 41.8781, longitude: -87.6298, name: 'Departure: Chicago', risk_level: 'low' },
        { sequence: 2, latitude: 40.1164, longitude: -88.2434, name: 'Waypoint 2', risk_level: 'severe' },
        { sequence: 3, latitude: 38.6270, longitude: -90.1994, name: 'Arrival: St. Louis', risk_level: 'low' },
      ],
    },
  ]

  test('prioritizes recommended route as default active route when no ID is selected', () => {
    const recommended = mockRoutes.find((r) => r.recommendation?.is_recommended)
    assert.ok(recommended)
    assert.strictEqual(recommended.route_id, 'route_primary')
  })

  test('selected route receives bold prominent style while alternative route receives muted dashed style', () => {
    const selectedStyle = getRouteStyle(mockRoutes[0], true, 0)
    const unselectedStyle = getRouteStyle(mockRoutes[1], false, 1)

    // Selected style: weight 6, high opacity, no dash
    assert.strictEqual(selectedStyle.weight, 6)
    assert.strictEqual(selectedStyle.opacity, 0.95)
    assert.strictEqual(selectedStyle.dashArray, null)

    // Alternative style: weight 4, muted opacity, dashed
    assert.strictEqual(unselectedStyle.weight, 4)
    assert.strictEqual(unselectedStyle.opacity, 0.55)
    assert.ok(unselectedStyle.dashArray.includes(','))
  })

  test('switching selected route updates active polyline and checkpoint associations', () => {
    let activeRouteId = 'route_primary'
    let activeRoute = mockRoutes.find((r) => r.route_id === activeRouteId)
    assert.strictEqual(activeRoute.display_name, 'Primary via I-55 S')

    // Simulate clicking alternative route
    activeRouteId = 'route_alt_1'
    activeRoute = mockRoutes.find((r) => r.route_id === activeRouteId)
    assert.strictEqual(activeRoute.display_name, 'Alternative via I-57 S')

    const checkpoints = extractRouteCheckpoints(activeRoute)
    assert.strictEqual(checkpoints[1].risk_level, 'severe')
  })
})

describe('Map Integration & Scenarios - Geometry Rendering with Mocked Data', () => {
  test('parses multi-segment corridor geometry without losing order or precision', () => {
    const mockCorridorGeo = {
      type: 'LineString',
      coordinates: [
        [-87.6298, 41.8781],
        [-89.6501, 39.7817],
        [-90.1994, 38.6270],
        [-92.2896, 34.7465], // Little Rock
        [-96.7970, 32.7767], // Dallas
      ],
    }

    const latLngs = parseRouteGeometry(mockCorridorGeo)

    assert.strictEqual(latLngs.length, 5)
    assert.deepStrictEqual(latLngs[0], [41.8781, -87.6298])
    assert.deepStrictEqual(latLngs[4], [32.7767, -96.7970])

    const bounds = getBoundsFromCoordinates(latLngs)
    assert.ok(bounds)
    assert.strictEqual(bounds[0][0], 32.7767) // minLat (Dallas)
    assert.strictEqual(bounds[1][0], 41.8781) // maxLat (Chicago)
  })
})

describe('Map Integration & Scenarios - Checkpoint Risk Markers & Legend', () => {
  const checkpointsWithRisks = [
    { sequence: 1, latitude: 41.878, longitude: -87.629, risk_level: 'low', name: 'Departure' },
    { sequence: 2, latitude: 40.500, longitude: -88.500, risk_level: 'moderate', name: 'Waypoint 2' },
    { sequence: 3, latitude: 39.000, longitude: -89.500, risk_level: 'high', name: 'Waypoint 3' },
    { sequence: 4, latitude: 37.500, longitude: -91.000, risk_level: 'severe', name: 'Waypoint 4' },
    { sequence: 5, latitude: 35.500, longitude: -93.000, risk_level: 'no_travel', name: 'Waypoint 5' },
    { sequence: 6, latitude: 33.500, longitude: -95.000, risk_level: null, name: 'Waypoint 6' }, // Missing risk
    { sequence: 7, latitude: 32.776, longitude: -96.797, risk_level: 'unknown', name: 'Arrival' },
  ]

  test('correctly maps each checkpoint to its visual risk attributes', () => {
    const meta1 = getRiskMeta(checkpointsWithRisks[0].risk_level)
    assert.strictEqual(meta1.key, 'low')
    assert.strictEqual(meta1.color, '#10b981')

    const meta2 = getRiskMeta(checkpointsWithRisks[1].risk_level)
    assert.strictEqual(meta2.key, 'moderate')
    assert.strictEqual(meta2.color, '#f59e0b')

    const meta3 = getRiskMeta(checkpointsWithRisks[2].risk_level)
    assert.strictEqual(meta3.key, 'high')
    assert.strictEqual(meta3.color, '#f97316')

    const meta4 = getRiskMeta(checkpointsWithRisks[3].risk_level)
    assert.strictEqual(meta4.key, 'severe')
    assert.strictEqual(meta4.color, '#ef4444')

    const meta5 = getRiskMeta(checkpointsWithRisks[4].risk_level)
    assert.strictEqual(meta5.key, 'no_travel')
    assert.strictEqual(meta5.color, '#991b1b')
  })

  test('CRITICAL RULE: missing or null risk is never treated as low, strictly mapped to unknown', () => {
    const missingRiskMeta = getRiskMeta(checkpointsWithRisks[5].risk_level)
    assert.strictEqual(missingRiskMeta.key, 'unknown')
    assert.notStrictEqual(missingRiskMeta.key, 'low')
    assert.strictEqual(missingRiskMeta.color, '#64748b')

    const unknownRiskMeta = getRiskMeta(checkpointsWithRisks[6].risk_level)
    assert.strictEqual(unknownRiskMeta.key, 'unknown')
  })

  test('legend dictionary covers all 6 required risk states', () => {
    const requiredKeys = ['low', 'moderate', 'high', 'severe', 'no_travel', 'unknown']
    requiredKeys.forEach((key) => {
      assert.ok(RISK_LEVEL_META[key], `Missing legend key: ${key}`)
      assert.ok(RISK_LEVEL_META[key].color)
      assert.ok(RISK_LEVEL_META[key].label)
    })
  })
})

describe('Map Integration & Scenarios - Missing Geometry & Empty Results', () => {
  test('gracefully handles route with missing geometry without crashing or drawing fake lines', () => {
    const routeWithoutGeometry = {
      route_id: 'no_geo_route',
      display_name: 'Corridor with missing polyline',
      geometry: null,
      checkpoints: [
        { sequence: 1, latitude: 41.8781, longitude: -87.6298, name: 'Origin' },
        { sequence: 2, latitude: 32.7767, longitude: -96.7970, name: 'Destination' },
      ],
    }

    const latLngs = parseRouteGeometry(routeWithoutGeometry.geometry)
    assert.strictEqual(latLngs.length, 0) // Never fabricates a line!

    // But checkpoints are still extracted for point markers
    const checkpoints = extractRouteCheckpoints(routeWithoutGeometry)
    assert.strictEqual(checkpoints.length, 2)
  })

  test('gracefully handles empty routes array', () => {
    const emptyRoutes = []
    const latLngs = emptyRoutes.flatMap((r) => parseRouteGeometry(r.geometry))
    assert.strictEqual(latLngs.length, 0)

    const bounds = getBoundsFromCoordinates(latLngs)
    assert.strictEqual(bounds, null)
  })

  test('gracefully rejects corrupted or empty coordinates dictionary in geometry', () => {
    assert.deepStrictEqual(parseRouteGeometry({ type: 'LineString', coordinates: null }), [])
    assert.deepStrictEqual(parseRouteGeometry({ type: 'Point', coordinates: [-87.6, 41.8] }), [])
    assert.deepStrictEqual(parseRouteGeometry({ coordinates: [[NaN, Infinity]] }), [])
  })
})
