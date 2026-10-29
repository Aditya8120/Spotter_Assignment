import { test, describe } from 'node:test'
import assert from 'node:assert'
import {
  generateForecastTimeline,
  matchCheckpointWeatherForTimestamp,
  getCheckpointLayerValue,
  WEATHER_LAYERS,
  LAYER_COLOR_SCALES,
} from './weatherLayers.js'

describe('Weather Heatmap & Forecast Timeline - Layer Switching', () => {
  const mockCheckpoint = {
    sequence: 3,
    latitude: 38.627,
    longitude: -90.199,
    name: 'Waypoint 3',
    estimated_arrival: '2026-10-30T10:00:00.000Z',
    risk_level: 'severe',
    risk_score: 80.0,
    weather: {
      timestamp: '2026-10-30T10:00:00.000Z',
      forecast_timestamp: '2026-10-30T10:00:00.000Z',
      data_availability: 'available',
      temperature: 32.0,
      wind_speed_mph: 46.0,
      wind_gust_mph: 54.0,
      precipitation_in_per_hour: 0.18,
      snowfall_in_per_hour: 2.50,
    },
  }

  const timestamp = '2026-10-30T10:00:00.000Z'

  test('switches dynamically between all 4 weather layers with proper units and colors', () => {
    // 1. Wind Layer
    const windRes = getCheckpointLayerValue(mockCheckpoint, 'wind', timestamp, 25000)
    assert.strictEqual(windRes.category, 'severe')
    assert.ok(windRes.displayValue.includes('46 mph'))
    assert.strictEqual(windRes.color, LAYER_COLOR_SCALES.wind.severe.color)

    // 2. Precipitation Layer
    const precipRes = getCheckpointLayerValue(mockCheckpoint, 'precipitation', timestamp, 40000)
    assert.strictEqual(precipRes.category, 'moderate') // 0.18 is moderate (0.10 - 0.25)
    assert.strictEqual(precipRes.displayValue, '0.18 in/h')
    assert.strictEqual(precipRes.color, LAYER_COLOR_SCALES.precipitation.moderate.color)

    // 3. Snowfall Layer
    const snowRes = getCheckpointLayerValue(mockCheckpoint, 'snowfall', timestamp, 40000)
    assert.strictEqual(snowRes.category, 'severe') // 2.50 is severe (2.00 - 3.00)
    assert.strictEqual(snowRes.displayValue, '2.50 in/h')
    assert.strictEqual(snowRes.color, LAYER_COLOR_SCALES.snowfall.severe.color)

    // 4. Overall Risk Layer
    const riskRes = getCheckpointLayerValue(mockCheckpoint, 'risk', timestamp, 40000)
    assert.strictEqual(riskRes.category, 'severe')
    assert.strictEqual(riskRes.color, LAYER_COLOR_SCALES.risk.severe.color)
  })

  test('preserves layer scale keys and descriptions across all 4 layers', () => {
    const layerKeys = ['wind', 'precipitation', 'snowfall', 'risk']
    layerKeys.forEach((key) => {
      assert.ok(WEATHER_LAYERS[key])
      assert.ok(WEATHER_LAYERS[key].unit)
      assert.ok(LAYER_COLOR_SCALES[key])
    })
  })
})

describe('Weather Heatmap & Forecast Timeline - Missing Weather Values & Stale Data Prevention', () => {
  test('missing core weather variables evaluate strictly to unknown, NEVER low', () => {
    const missingWindCp = {
      sequence: 1,
      estimated_arrival: '2026-10-30T08:00:00.000Z',
      weather: {
        timestamp: '2026-10-30T08:00:00.000Z',
        data_availability: 'partial',
        wind_speed_mph: null, // Missing wind
        precipitation_in_per_hour: 0.05,
      },
    }

    const res = getCheckpointLayerValue(missingWindCp, 'wind', '2026-10-30T08:00:00.000Z')
    assert.strictEqual(res.category, 'unknown')
    assert.notStrictEqual(res.category, 'low')
    assert.strictEqual(res.color, '#64748b')
    assert.strictEqual(res.displayValue, 'N/A')
  })

  test('prevents stale data reuse when timeline is scrubbed to unrecorded hours', () => {
    const cp = {
      sequence: 1,
      estimated_arrival: '2026-10-30T08:00:00.000Z',
      weather: {
        timestamp: '2026-10-30T08:00:00.000Z',
        forecast_timestamp: '2026-10-30T08:00:00.000Z',
        data_availability: 'available',
        wind_speed_mph: 30.0,
      },
    }

    // Scrub slider 10 hours later
    const futureMatch = matchCheckpointWeatherForTimestamp(cp, '2026-10-30T18:00:00.000Z')
    assert.strictEqual(futureMatch.isAvailable, false)
    assert.ok(futureMatch.reason.includes('Forecast data unavailable'))

    const futureLayer = getCheckpointLayerValue(cp, 'wind', '2026-10-30T18:00:00.000Z')
    assert.strictEqual(futureLayer.category, 'unknown')
    assert.strictEqual(futureLayer.isAvailable, false)
    assert.strictEqual(futureLayer.displayValue, 'N/A')
  })
})

describe('Weather Heatmap & Forecast Timeline - Route Selection Preservation', () => {
  test('scrubbing timeline and switching layers preserves selected route ID without resetting', () => {
    const mockState = {
      selectedRouteId: 'route_alternative_2',
      activeWeatherLayer: 'risk',
      selectedHourOffset: 0,
    }

    // 1. User switches weather layer
    const nextLayer = 'wind'
    const stateAfterLayerSwitch = { ...mockState, activeWeatherLayer: nextLayer }
    assert.strictEqual(stateAfterLayerSwitch.selectedRouteId, 'route_alternative_2')
    assert.strictEqual(stateAfterLayerSwitch.activeWeatherLayer, 'wind')

    // 2. User scrubs timeline to +18h
    const nextHour = 18
    const stateAfterScrub = { ...stateAfterLayerSwitch, selectedHourOffset: nextHour }
    assert.strictEqual(stateAfterScrub.selectedRouteId, 'route_alternative_2')
    assert.strictEqual(stateAfterScrub.selectedHourOffset, 18)
    assert.strictEqual(stateAfterScrub.activeWeatherLayer, 'wind')
  })
})

describe('Weather Heatmap & Forecast Timeline - Empty States', () => {
  test('gracefully handles empty routes or checkpoints without error', () => {
    const emptyCpList = []
    const timeline = generateForecastTimeline('2026-10-30T08:00:00.000Z', 48)

    assert.strictEqual(timeline.length, 49)
    assert.strictEqual(emptyCpList.length, 0)

    const nullCpRes = getCheckpointLayerValue(null, 'wind', timeline[0].isoTimestamp)
    assert.strictEqual(nullCpRes.category, 'unknown')
    assert.strictEqual(nullCpRes.isAvailable, false)
  })
})
