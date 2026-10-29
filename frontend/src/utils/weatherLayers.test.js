import { test, describe } from 'node:test'
import assert from 'node:assert'
import {
  evaluateWindCategory,
  evaluatePrecipitationCategory,
  evaluateSnowfallCategory,
  generateForecastTimeline,
  matchCheckpointWeatherForTimestamp,
  getCheckpointLayerValue,
  LAYER_COLOR_SCALES,
} from './weatherLayers.js'

describe('weatherLayers - Threshold Evaluations', () => {
  test('evaluates wind speed with load weight elevation', () => {
    // Normal load (40,000 lb)
    assert.strictEqual(evaluateWindCategory(15, 40000), 'low')
    assert.strictEqual(evaluateWindCategory(28, 40000), 'moderate')
    assert.strictEqual(evaluateWindCategory(38, 40000), 'high')
    assert.strictEqual(evaluateWindCategory(48, 40000), 'no_travel') // >30,000 lb elevates 45-54 to no_travel
    assert.strictEqual(evaluateWindCategory(60, 40000), 'no_travel')

    // Empty / Light truck (<= 30,000 lb at 48 mph remains severe)
    assert.strictEqual(evaluateWindCategory(48, 25000), 'severe')
    // Empty / Light trailer at 38 mph with > 40,000 lb elevates 35-44 to severe
    assert.strictEqual(evaluateWindCategory(38, 45000), 'severe')

    // Missing wind speed must return unknown, NEVER low
    assert.strictEqual(evaluateWindCategory(null, 40000), 'unknown')
    assert.strictEqual(evaluateWindCategory(undefined, 40000), 'unknown')
    assert.strictEqual(evaluateWindCategory('invalid', 40000), 'unknown')
  })

  test('evaluates precipitation intensity (in/h)', () => {
    assert.strictEqual(evaluatePrecipitationCategory(0.05), 'low')
    assert.strictEqual(evaluatePrecipitationCategory(0.15), 'moderate')
    assert.strictEqual(evaluatePrecipitationCategory(0.35), 'high')
    assert.strictEqual(evaluatePrecipitationCategory(0.75), 'severe')

    // Missing precipitation must return unknown, NEVER low
    assert.strictEqual(evaluatePrecipitationCategory(null), 'unknown')
    assert.strictEqual(evaluatePrecipitationCategory(undefined), 'unknown')
  })

  test('evaluates snowfall intensity (in/h)', () => {
    assert.strictEqual(evaluateSnowfallCategory(0.20), 'low')
    assert.strictEqual(evaluateSnowfallCategory(0.75), 'moderate')
    assert.strictEqual(evaluateSnowfallCategory(1.50), 'high')
    assert.strictEqual(evaluateSnowfallCategory(2.50), 'severe')
    assert.strictEqual(evaluateSnowfallCategory(3.50), 'no_travel')

    // Missing snowfall must return unknown, NEVER low
    assert.strictEqual(evaluateSnowfallCategory(null), 'unknown')
    assert.strictEqual(evaluateSnowfallCategory(undefined), 'unknown')
  })
})

describe('weatherLayers - generateForecastTimeline', () => {
  test('generates exactly 49 hourly slots for 0 to 48 hours', () => {
    const departure = '2026-10-30T08:00:00.000Z'
    const timeline = generateForecastTimeline(departure, 48)

    assert.strictEqual(timeline.length, 49)
    assert.strictEqual(timeline[0].hourOffset, 0)
    assert.strictEqual(timeline[0].label, 'Departure (T+0h)')
    assert.strictEqual(timeline[48].hourOffset, 48)
    assert.strictEqual(timeline[48].label, 'T+48h')
  })

  test('handles invalid departure string by defaulting to current time', () => {
    const timeline = generateForecastTimeline('not-a-date', 48)
    assert.strictEqual(timeline.length, 49)
    assert.ok(timeline[0].isoTimestamp)
  })
})

describe('weatherLayers - matchCheckpointWeatherForTimestamp', () => {
  test('matches checkpoint arrival weather when target timestamp is within arrival window', () => {
    const checkpoint = {
      sequence: 1,
      estimated_arrival: '2026-10-30T08:00:00.000Z',
      risk_level: 'moderate',
      weather: {
        timestamp: '2026-10-30T08:00:00.000Z',
        forecast_timestamp: '2026-10-30T08:00:00.000Z',
        data_availability: 'available',
        wind_speed_mph: 28,
        precipitation_in_per_hour: 0.15,
        snowfall_in_per_hour: 0.0,
      },
    }

    const match = matchCheckpointWeatherForTimestamp(checkpoint, '2026-10-30T08:00:00.000Z')
    assert.strictEqual(match.isAvailable, true)
    assert.strictEqual(match.weather.wind_speed_mph, 28)
  })

  test('marks checkpoint as unavailable when target timestamp is outside arrival window (prevents stale reuse)', () => {
    const checkpoint = {
      sequence: 1,
      estimated_arrival: '2026-10-30T08:00:00.000Z',
      risk_level: 'moderate',
      weather: {
        timestamp: '2026-10-30T08:00:00.000Z',
        forecast_timestamp: '2026-10-30T08:00:00.000Z',
        data_availability: 'available',
        wind_speed_mph: 28,
      },
    }

    // 12 hours later: observation should not be reused
    const match = matchCheckpointWeatherForTimestamp(checkpoint, '2026-10-30T20:00:00.000Z')
    assert.strictEqual(match.isAvailable, false)
    assert.ok(match.reason.includes('Forecast data unavailable'))
  })

  test('uses hourly_forecast array when present on checkpoint', () => {
    const checkpoint = {
      sequence: 2,
      estimated_arrival: '2026-10-30T08:00:00.000Z',
      weather: {
        wind_speed_mph: 10,
      },
      hourly_forecast: [
        { forecast_timestamp: '2026-10-30T08:00:00.000Z', wind_speed_mph: 15, risk_level: 'low' },
        { forecast_timestamp: '2026-10-30T12:00:00.000Z', wind_speed_mph: 42, risk_level: 'high' },
      ],
    }

    const match8 = matchCheckpointWeatherForTimestamp(checkpoint, '2026-10-30T08:00:00.000Z')
    assert.strictEqual(match8.isAvailable, true)
    assert.strictEqual(match8.weather.wind_speed_mph, 15)

    const match12 = matchCheckpointWeatherForTimestamp(checkpoint, '2026-10-30T12:00:00.000Z')
    assert.strictEqual(match12.isAvailable, true)
    assert.strictEqual(match12.weather.wind_speed_mph, 42)
    assert.strictEqual(match12.riskLevel, 'high')

    const matchUnrecorded = matchCheckpointWeatherForTimestamp(checkpoint, '2026-10-30T18:00:00.000Z')
    assert.strictEqual(matchUnrecorded.isAvailable, false)
  })
})

describe('weatherLayers - getCheckpointLayerValue', () => {
  const mockCheckpoint = {
    sequence: 1,
    estimated_arrival: '2026-10-30T08:00:00.000Z',
    risk_level: 'high',
    risk_score: 65.0,
    weather: {
      timestamp: '2026-10-30T08:00:00.000Z',
      data_availability: 'available',
      wind_speed_mph: 38.0,
      wind_gust_mph: 46.0,
      precipitation_in_per_hour: 0.35,
      snowfall_in_per_hour: 1.20,
    },
  }

  test('extracts wind layer values correctly', () => {
    const result = getCheckpointLayerValue(mockCheckpoint, 'wind', '2026-10-30T08:00:00.000Z', 40000)
    assert.strictEqual(result.category, 'high')
    assert.ok(result.displayValue.includes('38 mph'))
    assert.ok(result.displayValue.includes('G 46'))
    assert.strictEqual(result.color, LAYER_COLOR_SCALES.wind.high.color)
  })

  test('extracts precipitation layer values correctly', () => {
    const result = getCheckpointLayerValue(mockCheckpoint, 'precipitation', '2026-10-30T08:00:00.000Z')
    assert.strictEqual(result.category, 'high')
    assert.strictEqual(result.displayValue, '0.35 in/h')
  })

  test('extracts snowfall layer values correctly', () => {
    const result = getCheckpointLayerValue(mockCheckpoint, 'snowfall', '2026-10-30T08:00:00.000Z')
    assert.strictEqual(result.category, 'high')
    assert.strictEqual(result.displayValue, '1.20 in/h')
  })

  test('extracts overall risk layer values correctly', () => {
    const result = getCheckpointLayerValue(mockCheckpoint, 'risk', '2026-10-30T08:00:00.000Z')
    assert.strictEqual(result.category, 'high')
    assert.strictEqual(result.displayValue, 'High Risk')
  })

  test('returns unknown category when checkpoint has missing data for layer', () => {
    const emptyCheckpoint = { sequence: 2, weather: null }
    const result = getCheckpointLayerValue(emptyCheckpoint, 'wind', '2026-10-30T08:00:00.000Z')
    assert.strictEqual(result.category, 'unknown')
    assert.strictEqual(result.isAvailable, false)
    assert.strictEqual(result.color, '#64748b')
  })
})
