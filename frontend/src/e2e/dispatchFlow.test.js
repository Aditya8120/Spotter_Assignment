import { test, describe } from 'node:test'
import assert from 'node:assert'
import { buildRoutePlanPayload, planRoutes, ApiError } from '../services/api.js'
import { parseRouteGeometry, getBoundsFromCoordinates, extractRouteCheckpoints } from '../utils/mapUtils.js'
import {
  generateForecastTimeline,
  getCheckpointLayerValue,
  WEATHER_LAYERS,
} from '../utils/weatherLayers.js'

describe('End-to-End Dispatch Flow - Success Corridor Journey', () => {
  const originalFetch = global.fetch

  const mockPlannedApiResponse = {
    status: 'planned',
    message: 'Routes successfully calculated via Mapbox with Open-Meteo forecasts.',
    request_summary: {
      origin: { type: 'text', query: 'Chicago, IL' },
      destination: { type: 'text', query: 'Dallas, TX' },
      departure_datetime: '2026-10-30T08:00:00Z',
      load_weight_lb: 45000.0,
      checkpoint_interval_miles: 25,
    },
    recommendation_summary: {
      recommended_route_id: 'route_primary',
      all_routes_unsafe: false,
      total_options_evaluated: 2,
      executive_summary: 'Route Primary is recommended: 0.0 Severe miles, 0.0 High miles, lowest average risk score (14.2).',
      ranking_priority: [
        '1. Fewest miles classified as Severe',
        '2. Fewest miles classified as High',
        '3. Lowest average risk score',
        '4. Shortest travel time',
      ],
    },
    routes: [
      {
        route_id: 'route_primary',
        display_name: 'Primary via I-55 S',
        rank: 1,
        distance_miles: 924.5,
        duration_formatted: '14 hr 15 min',
        recommendation: {
          is_recommended: true,
          status: 'recommended',
          explanation: 'Safest corridor with calm weather and optimal duration.',
        },
        risk_assessment: {
          overall_risk_level: 'low',
          risk_score: 14.2,
          severe_risk_miles: 0.0,
          high_risk_miles: 0.0,
          moderate_risk_miles: 45.0,
          low_risk_miles: 879.5,
          no_travel_miles: 0.0,
          no_travel_warning: false,
        },
        geometry: {
          type: 'LineString',
          coordinates: [
            [-87.6298, 41.8781], // Chicago
            [-89.6501, 39.7817], // Springfield
            [-90.1994, 38.6270], // St. Louis
            [-92.2896, 34.7465], // Little Rock
            [-96.7970, 32.7767], // Dallas
          ],
        },
        checkpoints: [
          {
            sequence: 1,
            name: 'Departure: Chicago, IL',
            latitude: 41.8781,
            longitude: -87.6298,
            estimated_arrival: '2026-10-30T08:00:00Z',
            distance_from_origin_miles: 0.0,
            risk_level: 'low',
            risk_score: 10.0,
            weather: {
              timestamp: '2026-10-30T08:00:00Z',
              data_availability: 'available',
              temperature: 42.0,
              wind_speed_mph: 14.0,
              wind_gust_mph: 18.0,
              precipitation_rate_in_per_hour: 0.0,
              snowfall_rate_in_per_hour: 0.0,
            },
          },
          {
            sequence: 2,
            name: 'Waypoint 2 (Springfield)',
            latitude: 39.7817,
            longitude: -89.6501,
            estimated_arrival: '2026-10-30T11:30:00Z',
            distance_from_origin_miles: 200.0,
            risk_level: 'moderate',
            risk_score: 35.0,
            weather: {
              timestamp: '2026-10-30T11:30:00Z',
              data_availability: 'available',
              temperature: 48.0,
              wind_speed_mph: 28.0,
              wind_gust_mph: 34.0,
              precipitation_rate_in_per_hour: 0.12,
              snowfall_rate_in_per_hour: 0.0,
            },
          },
          {
            sequence: 3,
            name: 'Arrival: Dallas, TX',
            latitude: 32.7767,
            longitude: -96.7970,
            estimated_arrival: '2026-10-30T22:15:00Z',
            distance_from_origin_miles: 924.5,
            risk_level: 'low',
            risk_score: 10.0,
            weather: {
              timestamp: '2026-10-30T22:15:00Z',
              data_availability: 'available',
              temperature: 65.0,
              wind_speed_mph: 10.0,
              precipitation_rate_in_per_hour: 0.0,
              snowfall_rate_in_per_hour: 0.0,
            },
          },
        ],
      },
    ],
  }

  test('traces complete flow: input form payload -> API fetch -> map geometry -> checkpoint weather -> layer switching', async () => {
    // 1. Operator inputs form
    const formData = {
      origin: 'Chicago, IL',
      destination: 'Dallas, TX',
      departureDatetime: '2026-10-30T08:00:00Z',
      loadWeightLb: '45000',
      checkpointIntervalMiles: '25',
    }

    // 2. Client-side payload serialization
    const payload = buildRoutePlanPayload(formData)
    assert.strictEqual(payload.origin, 'Chicago, IL')
    assert.strictEqual(payload.load_weight_lb, 45000.0)

    // 3. Mock fetch response from POST /api/routes/
    global.fetch = async () => ({
      ok: true,
      status: 200,
      json: async () => mockPlannedApiResponse,
    })

    try {
      const response = await planRoutes(formData, { baseUrl: 'http://localhost:8000' })
      assert.strictEqual(response.status, 'planned')
      assert.strictEqual(response.routes.length, 1)

      const activeRoute = response.routes[0]
      assert.strictEqual(activeRoute.recommendation.is_recommended, true)

      // 4. Map geometry processing (inverts [lon, lat] to [lat, lon])
      const latLngs = parseRouteGeometry(activeRoute.geometry)
      assert.strictEqual(latLngs.length, 5)
      assert.deepStrictEqual(latLngs[0], [41.8781, -87.6298]) // Chicago
      assert.deepStrictEqual(latLngs[4], [32.7767, -96.7970]) // Dallas

      // 5. Bounds calculation
      const bounds = getBoundsFromCoordinates(latLngs)
      assert.strictEqual(bounds[0][0], 32.7767) // minLat
      assert.strictEqual(bounds[1][0], 41.8781) // maxLat

      // 6. Checkpoint extraction
      const checkpoints = extractRouteCheckpoints(activeRoute)
      assert.strictEqual(checkpoints.length, 3)

      // 7. Timeline generation (0 to 48 hours)
      const timeline = generateForecastTimeline(payload.departure_datetime, 48)
      assert.strictEqual(timeline.length, 49)

      // 8. Layer evaluation at Departure (T+0h)
      const t0 = timeline[0].isoTimestamp
      const cp1Wind = getCheckpointLayerValue(checkpoints[0], 'wind', t0, payload.load_weight_lb)
      assert.strictEqual(cp1Wind.category, 'low')
      assert.ok(cp1Wind.displayValue.includes('14 mph'))

      const cp1Precip = getCheckpointLayerValue(checkpoints[0], 'precipitation', t0, payload.load_weight_lb)
      assert.strictEqual(cp1Precip.category, 'low')

      // 9. Layer evaluation for Waypoint 2 at T+3h (Springfield arrival window)
      const t3 = timeline[3].isoTimestamp
      const cp2Wind = getCheckpointLayerValue(checkpoints[1], 'wind', t3, payload.load_weight_lb)
      assert.strictEqual(cp2Wind.category, 'moderate')
      assert.ok(cp2Wind.displayValue.includes('28 mph'))

      // 10. Verify layer switching among all 4 layers
      Object.keys(WEATHER_LAYERS).forEach((layerKey) => {
        const layerRes = getCheckpointLayerValue(checkpoints[1], layerKey, t3, payload.load_weight_lb)
        assert.ok(layerRes.category)
        assert.ok(layerRes.color)
      })
    } finally {
      global.fetch = originalFetch
    }
  })
})

describe('End-to-End Dispatch Flow - Error & Lifecycle States', () => {
  const originalFetch = global.fetch

  test('HTTP 503 provider_not_configured returns pending setup banner without fabricating routes', async () => {
    global.fetch = async () => ({
      ok: false,
      status: 503,
      json: async () => ({
        status: 'error',
        code: 'provider_not_configured',
        message: 'Mapbox access token is not configured.',
      }),
    })

    try {
      const result = await planRoutes(
        { origin: 'A', destination: 'B', departureDatetime: '2026-10-30T08:00', loadWeightLb: 40000 },
        { baseUrl: 'http://localhost:8000' }
      )
      assert.strictEqual(result._isPendingSetup, true)
      assert.strictEqual(result.code, 'provider_not_configured')
      assert.ok(result.message.includes('Backend Setup Pending'))
    } finally {
      global.fetch = originalFetch
    }
  })

  test('HTTP 400 validation error maps field errors and rejects request cleanly', async () => {
    global.fetch = async () => ({
      ok: false,
      status: 400,
      json: async () => ({
        origin: ['Origin location is required.'],
      }),
    })

    try {
      await planRoutes(
        { origin: 'A', destination: 'B', departureDatetime: '2026-10-30T08:00', loadWeightLb: 40000 },
        { baseUrl: 'http://localhost:8000' }
      )
      assert.fail('Should throw ApiError')
    } catch (err) {
      assert.ok(err instanceof ApiError)
      assert.strictEqual(err.status, 400)
      assert.ok(err.fieldErrors.origin)
    } finally {
      global.fetch = originalFetch
    }
  })

  test('Network failure provides clear troubleshooting command', async () => {
    global.fetch = async () => {
      throw new TypeError('Failed to fetch')
    }

    try {
      await planRoutes(
        { origin: 'A', destination: 'B', departureDatetime: '2026-10-30T08:00', loadWeightLb: 40000 },
        { baseUrl: 'http://localhost:8000' }
      )
      assert.fail('Should throw ApiError')
    } catch (err) {
      assert.ok(err instanceof ApiError)
      assert.strictEqual(err.status, 0)
      assert.ok(err.message.includes('http://localhost:8000'))
    } finally {
      global.fetch = originalFetch
    }
  })
})
