import { test, describe } from 'node:test'
import assert from 'node:assert'
import { DEMO_CORRIDOR_PLAN } from '../data/demoCorridor.js'
import { parseRouteGeometry, getBoundsFromCoordinates, extractRouteCheckpoints } from '../utils/mapUtils.js'
import { getCheckpointLayerValue, WEATHER_LAYERS } from '../utils/weatherLayers.js'

describe('Demonstration Corridor Fixture & Transparency Verification', () => {
  test('DEMO_CORRIDOR_PLAN explicitly declares simulated data and contains expected corridors', () => {
    assert.strictEqual(DEMO_CORRIDOR_PLAN.status, 'planned')
    assert.strictEqual(DEMO_CORRIDOR_PLAN.is_demo_data, true)
    assert.ok(DEMO_CORRIDOR_PLAN.message.includes('DEMONSTRATION MODE'))
    assert.strictEqual(DEMO_CORRIDOR_PLAN.routes.length, 2)
  })

  test('Primary demo route has valid coordinates, bounds, and passes layer evaluations', () => {
    const primary = DEMO_CORRIDOR_PLAN.routes[0]
    assert.strictEqual(primary.route_id, 'demo_route_primary')
    assert.strictEqual(primary.recommendation.is_recommended, true)

    // Geometry
    const latLngs = parseRouteGeometry(primary.geometry)
    assert.strictEqual(latLngs.length, 8)
    assert.deepStrictEqual(latLngs[0], [41.8781, -87.6298]) // Chicago
    assert.deepStrictEqual(latLngs[7], [32.7767, -96.7970]) // Dallas

    // Bounds
    const bounds = getBoundsFromCoordinates(latLngs)
    assert.ok(bounds)
    assert.strictEqual(bounds[0][0], 32.7767)
    assert.strictEqual(bounds[1][0], 41.8781)

    // Checkpoints
    const checkpoints = extractRouteCheckpoints(primary)
    assert.strictEqual(checkpoints.length, 7)

    // Layer values at departure
    Object.keys(WEATHER_LAYERS).forEach((layer) => {
      const meta = getCheckpointLayerValue(checkpoints[0], layer, '2026-10-30T08:00:00Z', 45000)
      assert.ok(meta.category)
      assert.ok(meta.color)
      assert.ok(meta.displayValue)
    })
  })

  test('Alternative demo route correctly reflects moderate/high hazard segments', () => {
    const alt = DEMO_CORRIDOR_PLAN.routes[1]
    assert.strictEqual(alt.route_id, 'demo_route_alternative')
    assert.strictEqual(alt.recommendation.is_recommended, false)
    assert.strictEqual(alt.risk_assessment.high_risk_miles, 38.0)

    const latLngs = parseRouteGeometry(alt.geometry)
    assert.strictEqual(latLngs.length, 7)
  })
})
