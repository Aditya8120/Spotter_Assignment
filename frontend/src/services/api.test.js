import { test, describe } from 'node:test'
import assert from 'node:assert'
import { buildRoutePlanPayload, planRoutes, checkHealth, ApiError } from './api.js'

describe('API Service - buildRoutePlanPayload', () => {
  test('correctly transforms valid form data to Django request schema', () => {
    const formData = {
      origin: '  Chicago, IL  ',
      destination: '  Dallas, TX  ',
      departureDatetime: '2026-10-30T08:00',
      loadWeightLb: '45000',
      checkpointIntervalMiles: '25',
    }

    const payload = buildRoutePlanPayload(formData)

    assert.strictEqual(payload.origin, 'Chicago, IL')
    assert.strictEqual(payload.destination, 'Dallas, TX')
    assert.strictEqual(payload.load_weight_lb, 45000.0)
    assert.strictEqual(payload.checkpoint_interval_miles, 25)
    assert.ok(payload.departure_datetime.includes('2026-10-30'))
    assert.ok(payload.departure_datetime.endsWith('Z'))
  })

  test('defaults checkpoint interval to 25 if not provided or empty', () => {
    const payload = buildRoutePlanPayload({
      origin: 'Denver, CO',
      destination: 'Salt Lake City, UT',
      departureDatetime: '2026-10-30T10:00:00Z',
      loadWeightLb: 35000,
    })

    assert.strictEqual(payload.checkpoint_interval_miles, 25)
  })

  test('throws error if load weight is zero or negative', () => {
    assert.throws(() => {
      buildRoutePlanPayload({
        origin: 'A',
        destination: 'B',
        departureDatetime: '2026-10-30T08:00',
        loadWeightLb: '0',
      })
    }, /Load weight must be a positive number/)

    assert.throws(() => {
      buildRoutePlanPayload({
        origin: 'A',
        destination: 'B',
        departureDatetime: '2026-10-30T08:00',
        loadWeightLb: '-500',
      })
    }, /Load weight must be a positive number/)
  })

  test('throws error if departure datetime is invalid', () => {
    assert.throws(() => {
      buildRoutePlanPayload({
        origin: 'A',
        destination: 'B',
        departureDatetime: 'not-a-date',
        loadWeightLb: 30000,
      })
    }, /Invalid departure date and time/)
  })
})

describe('API Service - planRoutes HTTP Networking', () => {
  const originalFetch = global.fetch

  test('successfully parses 200 OK planned routes response', async () => {
    const mockApiResponse = {
      status: 'planned',
      message: 'Routes successfully calculated',
      routes: [
        {
          route_id: 'mapbox_1',
          display_name: 'Primary Route',
          rank: 1,
          distance_miles: 500.0,
          recommendation: { is_recommended: true, status: 'recommended' },
        },
      ],
      recommendation_summary: {
        recommended_route_id: 'mapbox_1',
        all_routes_unsafe: false,
      },
    }

    global.fetch = async (url, options) => {
      assert.ok(url.includes('/api/routes/'))
      assert.strictEqual(options.method, 'POST')
      const body = JSON.parse(options.body)
      assert.strictEqual(body.origin, 'Chicago, IL')

      return {
        ok: true,
        status: 200,
        json: async () => mockApiResponse,
      }
    }

    try {
      const data = await planRoutes(
        {
          origin: 'Chicago, IL',
          destination: 'Dallas, TX',
          departureDatetime: '2026-10-30T08:00',
          loadWeightLb: 40000,
        },
        { baseUrl: 'http://localhost:8000' }
      )

      assert.strictEqual(data.status, 'planned')
      assert.strictEqual(data.routes.length, 1)
      assert.strictEqual(data.routes[0].route_id, 'mapbox_1')
      assert.strictEqual(data.recommendation_summary.recommended_route_id, 'mapbox_1')
    } finally {
      global.fetch = originalFetch
    }
  })

  test('handles HTTP 503 provider_not_configured gracefully as pending setup', async () => {
    global.fetch = async () => ({
      ok: false,
      status: 503,
      json: async () => ({
        status: 'error',
        code: 'provider_not_configured',
        message: 'Routing provider is not configured. Missing MAPBOX_ACCESS_TOKEN in server environment.',
      }),
    })

    try {
      const result = await planRoutes(
        {
          origin: 'Chicago, IL',
          destination: 'Dallas, TX',
          departureDatetime: '2026-10-30T08:00',
          loadWeightLb: 40000,
        },
        { baseUrl: 'http://localhost:8000' }
      )

      assert.strictEqual(result._isPendingSetup, true)
      assert.strictEqual(result.code, 'provider_not_configured')
      assert.ok(result.message.includes('Backend Setup Pending'))
    } finally {
      global.fetch = originalFetch
    }
  })

  test('handles HTTP 400 validation errors and formats field error mappings', async () => {
    global.fetch = async () => ({
      ok: false,
      status: 400,
      json: async () => ({
        destination: ['Destination cannot be identical to origin.'],
      }),
    })

    try {
      await planRoutes(
        {
          origin: 'Chicago, IL',
          destination: 'Chicago, IL',
          departureDatetime: '2026-10-30T08:00',
          loadWeightLb: 40000,
        },
        { baseUrl: 'http://localhost:8000' }
      )
      assert.fail('Should have thrown ApiError')
    } catch (err) {
      assert.ok(err instanceof ApiError)
      assert.strictEqual(err.status, 400)
      assert.ok(err.fieldErrors.destination.includes('identical to origin'))
    } finally {
      global.fetch = originalFetch
    }
  })

  test('handles HTTP 404 no route found error', async () => {
    global.fetch = async () => ({
      ok: false,
      status: 404,
      json: async () => ({
        status: 'error',
        code: 'no_route_found',
        message: 'No driving route could be found.',
      }),
    })

    try {
      await planRoutes(
        {
          origin: 'Hawaii',
          destination: 'California',
          departureDatetime: '2026-10-30T08:00',
          loadWeightLb: 35000,
        },
        { baseUrl: 'http://localhost:8000' }
      )
      assert.fail('Should have thrown ApiError')
    } catch (err) {
      assert.ok(err instanceof ApiError)
      assert.strictEqual(err.status, 404)
      assert.strictEqual(err.code, 'no_route_found')
    } finally {
      global.fetch = originalFetch
    }
  })

  test('handles network failure (TypeError / connection refused) with clear guidance', async () => {
    global.fetch = async () => {
      throw new TypeError('Failed to fetch')
    }

    try {
      await planRoutes(
        {
          origin: 'Chicago, IL',
          destination: 'Dallas, TX',
          departureDatetime: '2026-10-30T08:00',
          loadWeightLb: 35000,
        },
        { baseUrl: 'http://localhost:8000' }
      )
      assert.fail('Should have thrown ApiError')
    } catch (err) {
      assert.ok(err instanceof ApiError)
      assert.strictEqual(err.status, 0)
      assert.strictEqual(err.code, 'network_error')
      assert.ok(err.message.includes('Ensure the Django backend server is running'))
    } finally {
      global.fetch = originalFetch
    }
  })
})

describe('API Service - checkHealth', () => {
  const originalFetch = global.fetch

  test('returns status ok when server responds', async () => {
    global.fetch = async (url) => {
      assert.ok(url.includes('/api/health/'))
      return {
        ok: true,
        json: async () => ({ status: 'ok' }),
      }
    }

    try {
      const data = await checkHealth({ baseUrl: 'http://localhost:8000' })
      assert.strictEqual(data.status, 'ok')
    } finally {
      global.fetch = originalFetch
    }
  })
})
