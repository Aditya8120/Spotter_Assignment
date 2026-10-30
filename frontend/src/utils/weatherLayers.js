/**
 * Weather Layer Definitions, Color Scales, Category Evaluation,
 * and 0–48h Forecast Timeline Utilities for Corridor Heatmaps.
 */

export const WEATHER_LAYERS = {
  risk: {
    key: 'risk',
    label: 'Overall Risk',
    icon: '🛡️',
    unit: 'Category',
    description: 'Composite hazard risk governed by most severe condition and truck load weight.',
  },
  wind: {
    key: 'wind',
    label: 'Wind Speed',
    icon: '💨',
    unit: 'mph',
    description: 'Sustained wind speed and gusts with commercial vehicle tip-over thresholds.',
  },
  precipitation: {
    key: 'precipitation',
    label: 'Precipitation',
    icon: '🌧️',
    unit: 'in/h',
    description: '1-hour rainfall intensity rate and hydroplaning hazard evaluation.',
  },
  snowfall: {
    key: 'snowfall',
    label: 'Snowfall',
    icon: '❄️',
    unit: 'in/h',
    description: 'Snow accumulation rate, winter traction impairment, and whiteout risk.',
  },
}

/**
 * Color scales for each weather layer.
 * All layers include an explicit 'unknown' category for missing or unmeasured data.
 * CRITICAL RULE: Missing data is NEVER styled as 'low'.
 */
export const LAYER_COLOR_SCALES = {
  wind: {
    low: { label: 'Low (<25 mph)', color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.45)', threshold: '< 25 mph' },
    moderate: { label: 'Moderate (25–34 mph)', color: '#f59e0b', bgColor: 'rgba(245, 158, 11, 0.55)', threshold: '25–34 mph' },
    high: { label: 'High (35–44 mph)', color: '#f97316', bgColor: 'rgba(249, 115, 22, 0.65)', threshold: '35–44 mph' },
    severe: { label: 'Severe (45–54 mph)', color: '#ef4444', bgColor: 'rgba(239, 68, 68, 0.75)', threshold: '45–54 mph' },
    no_travel: { label: 'No Travel (≥55 mph)', color: '#991b1b', bgColor: 'rgba(153, 27, 27, 0.85)', threshold: '≥ 55 mph' },
    unknown: { label: 'Data Unavailable', color: '#64748b', bgColor: 'rgba(100, 116, 139, 0.35)', threshold: 'Missing / Pending' },
  },
  precipitation: {
    low: { label: 'Low (<0.10 in/h)', color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.45)', threshold: '< 0.10 in/h' },
    moderate: { label: 'Moderate (0.10–0.25 in/h)', color: '#f59e0b', bgColor: 'rgba(245, 158, 11, 0.55)', threshold: '0.10–0.25 in/h' },
    high: { label: 'High (>0.25–0.50 in/h)', color: '#f97316', bgColor: 'rgba(249, 115, 22, 0.65)', threshold: '> 0.25–0.50 in/h' },
    severe: { label: 'Severe (>0.50 in/h)', color: '#ef4444', bgColor: 'rgba(239, 68, 68, 0.75)', threshold: '> 0.50 in/h' },
    unknown: { label: 'Data Unavailable', color: '#64748b', bgColor: 'rgba(100, 116, 139, 0.35)', threshold: 'Missing / Pending' },
  },
  snowfall: {
    low: { label: 'Low (<0.50 in/h)', color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.45)', threshold: '< 0.50 in/h' },
    moderate: { label: 'Moderate (0.50–1.00 in/h)', color: '#f59e0b', bgColor: 'rgba(245, 158, 11, 0.55)', threshold: '0.50–1.00 in/h' },
    high: { label: 'High (>1.00–2.00 in/h)', color: '#f97316', bgColor: 'rgba(249, 115, 22, 0.65)', threshold: '> 1.00–2.00 in/h' },
    severe: { label: 'Severe (>2.00–3.00 in/h)', color: '#ef4444', bgColor: 'rgba(239, 68, 68, 0.75)', threshold: '> 2.00–3.00 in/h' },
    no_travel: { label: 'No Travel (>3.00 in/h)', color: '#991b1b', bgColor: 'rgba(153, 27, 27, 0.85)', threshold: '> 3.00 in/h' },
    unknown: { label: 'Data Unavailable', color: '#64748b', bgColor: 'rgba(100, 116, 139, 0.35)', threshold: 'Missing / Pending' },
  },
  risk: {
    low: { label: 'Low Risk', color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.45)', threshold: 'All hazards Low' },
    moderate: { label: 'Moderate Risk', color: '#f59e0b', bgColor: 'rgba(245, 158, 11, 0.55)', threshold: 'Advisory conditions' },
    high: { label: 'High Risk', color: '#f97316', bgColor: 'rgba(249, 115, 22, 0.65)', threshold: 'Warning conditions' },
    severe: { label: 'Severe Risk', color: '#ef4444', bgColor: 'rgba(239, 68, 68, 0.75)', threshold: 'Severe hazards / elevated load risk' },
    no_travel: { label: 'No Travel Advisory', color: '#991b1b', bgColor: 'rgba(153, 27, 27, 0.85)', threshold: 'Extreme winds / impassable roads' },
    unknown: { label: 'Unknown / Pending', color: '#64748b', bgColor: 'rgba(100, 116, 139, 0.35)', threshold: 'Missing / Pending' },
  },
}

/**
 * Evaluates wind speed against exact assignment thresholds and truck load weight.
 *
 * Rules:
 * - >= 55 mph: No Travel (for all loads)
 * - 45 to <55 mph: Severe (or No Travel if load weight > 30,000 lb)
 * - 35 to <45 mph: High (or Severe if load weight > 40,000 lb)
 * - 25 to <35 mph: Moderate
 * - < 25 mph: Low
 * - null/undefined: unknown (NEVER Low)
 */
export function evaluateWindCategory(speedMph, loadWeightLb = 40000) {
  if (speedMph === null || speedMph === undefined || !Number.isFinite(Number(speedMph))) {
    return 'unknown'
  }
  const speed = Number(speedMph)
  const weight = Number(loadWeightLb) || 40000

  if (speed >= 55.0) return 'no_travel'
  if (speed >= 45.0) {
    return weight > 30000 ? 'no_travel' : 'severe'
  }
  if (speed >= 35.0) {
    return weight > 40000 ? 'severe' : 'high'
  }
  if (speed >= 25.0) return 'moderate'
  return 'low'
}

/**
 * Evaluates precipitation rate (in/h) against exact assignment thresholds:
 * - > 0.50 in/h: Severe
 * - > 0.25 to 0.50 in/h: High
 * - 0.10 to 0.25 in/h: Moderate
 * - < 0.10 in/h: Low
 * - null/undefined: unknown (NEVER Low)
 */
export function evaluatePrecipitationCategory(rateInPerHour) {
  if (rateInPerHour === null || rateInPerHour === undefined || !Number.isFinite(Number(rateInPerHour))) {
    return 'unknown'
  }
  const rate = Number(rateInPerHour)
  if (rate > 0.50) return 'severe'
  if (rate > 0.25) return 'high'
  if (rate >= 0.10) return 'moderate'
  return 'low'
}

/**
 * Evaluates snowfall rate (in/h) against exact assignment thresholds:
 * - > 3.00 in/h: No Travel (Whiteout)
 * - > 2.00 to 3.00 in/h: Severe
 * - > 1.00 to 2.00 in/h: High
 * - 0.50 to 1.00 in/h: Moderate
 * - < 0.50 in/h: Low
 * - null/undefined: unknown (NEVER Low)
 */
export function evaluateSnowfallCategory(rateInPerHour) {
  if (rateInPerHour === null || rateInPerHour === undefined || !Number.isFinite(Number(rateInPerHour))) {
    return 'unknown'
  }
  const rate = Number(rateInPerHour)
  if (rate > 3.00) return 'no_travel'
  if (rate > 2.00) return 'severe'
  if (rate > 1.00) return 'high'
  if (rate >= 0.50) return 'moderate'
  return 'low'
}

/**
 * Generates an array of 49 hourly timestamps representing 0 to 48 hours
 * relative to the base departure date/time.
 */
export function generateForecastTimeline(baseDepartureIso, hoursCount = 48) {
  let baseDate
  try {
    baseDate = baseDepartureIso ? new Date(baseDepartureIso) : new Date()
    if (isNaN(baseDate.getTime())) {
      baseDate = new Date()
    }
  } catch {
    baseDate = new Date()
  }

  // Snap to top of the hour
  const startHour = new Date(baseDate)
  startHour.setMinutes(0, 0, 0)

  const slots = []
  for (let h = 0; h <= hoursCount; h++) {
    const slotTime = new Date(startHour.getTime() + h * 3600 * 1000)
    slots.push({
      hourOffset: h,
      isoTimestamp: slotTime.toISOString(),
      label: h === 0 ? 'Departure (T+0h)' : `T+${h}h`,
      displayTime: slotTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      displayDate: slotTime.toLocaleDateString([], { month: 'short', day: 'numeric' }),
    })
  }

  return slots
}

/**
 * Resolves weather observation for a checkpoint at a requested forecast timestamp.
 *
 * Checks:
 * 1. If checkpoint contains an `hourly_forecast` array, finds the exact slot matching targetTimestamp.
 * 2. If checkpoint only has single arrival weather (`checkpoint.weather`):
 *    - Checks if targetTimestamp falls within +/- 1 hour of the arrival time or forecast_timestamp.
 *    - If yes, returns that observation with `isMatchingArrival: true`.
 *    - If no, returns an explicit `unavailable` result with `isMatchingArrival: false`.
 *
 * CRITICAL RULE: Never reuses a stale observation for an unrelated timestamp without identifying it.
 */
export function matchCheckpointWeatherForTimestamp(checkpoint, targetTimestamp) {
  if (!checkpoint || !checkpoint.weather) {
    return {
      isAvailable: false,
      reason: 'No weather observation attached to this checkpoint.',
      weather: null,
      riskLevel: 'unknown',
    }
  }

  const weather = checkpoint.weather

  // Case 1: Checkpoint has full hourly_forecast array
  if (Array.isArray(checkpoint.hourly_forecast) && checkpoint.hourly_forecast.length > 0) {
    const targetDt = new Date(targetTimestamp).getTime()
    // Find closest hourly entry within 60 minutes
    const match = checkpoint.hourly_forecast.find((entry) => {
      if (!entry.forecast_timestamp) return false
      const entryDt = new Date(entry.forecast_timestamp).getTime()
      return Math.abs(entryDt - targetDt) <= 3600 * 1000
    })

    if (match) {
      return {
        isAvailable: true,
        reason: null,
        weather: match,
        riskLevel: match.risk_level || checkpoint.risk_level || 'unknown',
      }
    }

    return {
      isAvailable: false,
      reason: `No hourly forecast entry for selected timestamp ${targetTimestamp}.`,
      weather: null,
      riskLevel: 'unknown',
    }
  }

  // Case 2: Checkpoint has single arrival-time weather observation
  const arrivalIso = checkpoint.estimated_arrival || weather.timestamp || weather.forecast_timestamp
  if (!arrivalIso) {
    return {
      isAvailable: false,
      reason: 'Checkpoint is missing estimated arrival timestamp.',
      weather: null,
      riskLevel: 'unknown',
    }
  }

  const arrivalDt = new Date(arrivalIso).getTime()
  const targetDt = new Date(targetTimestamp).getTime()
  const diffHours = Math.abs(arrivalDt - targetDt) / (3600 * 1000)

  // Within 1.5 hours of arrival window: valid matching observation
  if (diffHours <= 1.5) {
    return {
      isAvailable: weather.data_availability !== 'unavailable' && weather.data_availability !== 'out_of_forecast_horizon',
      reason: weather.data_availability === 'unavailable' ? 'Weather provider reported unavailable.' : null,
      weather,
      riskLevel: checkpoint.risk_level || 'unknown',
      isArrivalObservation: true,
    }
  }

  // Outside arrival observation window: forecast data unavailable for this hour
  return {
    isAvailable: false,
    reason: `Forecast data unavailable for this hour. Arrival weather was sampled at ${new Date(arrivalIso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}.`,
    weather: null,
    riskLevel: 'unknown',
    isArrivalObservation: false,
  }
}

/**
 * Extracts the layer-specific metric value, formatted display string,
 * and category key ('low' | 'moderate' | 'high' | 'severe' | 'no_travel' | 'unknown')
 * for a checkpoint at a target timestamp.
 */
export function getCheckpointLayerValue(checkpoint, layerKey, targetTimestamp, loadWeightLb = 40000) {
  const matchResult = matchCheckpointWeatherForTimestamp(checkpoint, targetTimestamp)

  if (!matchResult.isAvailable || !matchResult.weather) {
    const scale = LAYER_COLOR_SCALES[layerKey] || LAYER_COLOR_SCALES.risk
    return {
      category: 'unknown',
      value: null,
      displayValue: 'N/A',
      color: scale.unknown.color,
      bgColor: scale.unknown.bgColor,
      label: scale.unknown.label,
      isAvailable: false,
      reason: matchResult.reason || 'Data unavailable for this timestamp',
    }
  }

  const w = matchResult.weather
  const scale = LAYER_COLOR_SCALES[layerKey] || LAYER_COLOR_SCALES.risk
  let category = 'unknown'
  let value = null
  let displayValue = 'N/A'

  switch (layerKey) {
    case 'wind': {
      value = w.wind_speed_mph
      category = evaluateWindCategory(value, loadWeightLb)
      displayValue = value != null ? `${Math.round(value)} mph${w.wind_gust_mph ? ` (G ${Math.round(w.wind_gust_mph)})` : ''}` : 'N/A'
      break
    }
    case 'precipitation': {
      value = w.precipitation_rate_in_per_hour != null ? w.precipitation_rate_in_per_hour : w.precipitation_in_per_hour
      category = evaluatePrecipitationCategory(value)
      displayValue = value != null ? `${Number(value).toFixed(2)} in/h` : 'N/A'
      break
    }
    case 'snowfall': {
      value = w.snowfall_rate_in_per_hour != null ? w.snowfall_rate_in_per_hour : w.snowfall_in_per_hour
      category = evaluateSnowfallCategory(value)
      displayValue = value != null ? `${Number(value).toFixed(2)} in/h` : 'N/A'
      break
    }
    case 'risk':
    default: {
      category = (matchResult.riskLevel || 'unknown').toLowerCase().replace(/[\s-]+/g, '_')
      if ((!scale[category] || category === 'unknown') && w) {
        if (w.wind_speed_mph != null || w.precipitation_in_per_hour != null || w.snowfall_in_per_hour != null) {
          const windCat = evaluateWindCategory(w.wind_speed_mph, loadWeightLb)
          const precipCat = evaluatePrecipitationCategory(w.precipitation_in_per_hour != null ? w.precipitation_in_per_hour : w.precipitation_rate_in_per_hour)
          const snowCat = evaluateSnowfallCategory(w.snowfall_in_per_hour != null ? w.snowfall_in_per_hour : w.snowfall_rate_in_per_hour)
          const severityOrder = ['no_travel', 'severe', 'high', 'moderate', 'low']
          category = severityOrder.find((c) => c === windCat || c === precipCat || c === snowCat) || 'low'
        }
      }
      if (!scale[category]) category = 'unknown'
      value = checkpoint.risk_score
      displayValue = scale[category]?.label || 'Unknown'
      break
    }
  }

  const colorMeta = scale[category] || scale.unknown

  return {
    category,
    value,
    displayValue,
    color: colorMeta.color,
    bgColor: colorMeta.bgColor,
    label: colorMeta.label,
    isAvailable: category !== 'unknown',
    reason: null,
  }
}
