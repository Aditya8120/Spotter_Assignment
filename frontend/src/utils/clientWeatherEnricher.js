import {
  evaluateWindCategory,
  evaluatePrecipitationCategory,
  evaluateSnowfallCategory,
} from './weatherLayers.js'

const WMO_WEATHER_CODES = {
  0: 'Clear sky',
  1: 'Mainly clear',
  2: 'Partly cloudy',
  3: 'Overcast',
  45: 'Fog',
  48: 'Depositing rime fog',
  51: 'Light drizzle',
  53: 'Moderate drizzle',
  55: 'Dense drizzle',
  56: 'Light freezing drizzle',
  57: 'Dense freezing drizzle',
  61: 'Slight rain',
  63: 'Moderate rain',
  65: 'Heavy rain',
  66: 'Light freezing rain',
  67: 'Heavy freezing rain',
  71: 'Slight snow fall',
  73: 'Moderate snow fall',
  75: 'Heavy snow fall',
  77: 'Snow grains',
  80: 'Slight rain showers',
  81: 'Moderate rain showers',
  82: 'Violent rain showers',
  85: 'Slight snow showers',
  86: 'Heavy snow showers',
  95: 'Thunderstorm',
  96: 'Thunderstorm with slight hail',
  99: 'Thunderstorm with heavy hail',
}

/**
 * Checks if route checkpoints have missing weather (e.g., when a shared cloud hosting IP like Render
 * encounters temporary Open-Meteo 429 rate limiting).
 * If unassessed checkpoints are found, fetches live Open-Meteo forecasts directly from the client's
 * unthrottled residential browser connection and enriches all checkpoints and risk calculations.
 */
export async function enrichRoutesWithClientWeather(routesData, loadWeightLb = 40000) {
  if (!routesData || !Array.isArray(routesData.routes) || routesData.routes.length === 0) {
    return routesData
  }

  // Check if any route has unassessed or unavailable checkpoints
  const needsEnrichment = routesData.routes.some((r) =>
    r.checkpoints?.some(
      (cp) =>
        !cp.weather ||
        cp.weather.data_availability === 'unavailable' ||
        cp.risk_level === 'unknown' ||
        !Array.isArray(cp.hourly_forecast) ||
        cp.hourly_forecast.length === 0
    )
  )

  if (!needsEnrichment) {
    return routesData
  }

  try {
    // 1. Gather unique coordinates across all routes
    const coordMap = new Map()
    const coordList = []

    for (const route of routesData.routes) {
      for (const cp of route.checkpoints || []) {
        if (Number.isFinite(cp.latitude) && Number.isFinite(cp.longitude)) {
          const key = `${cp.latitude.toFixed(3)},${cp.longitude.toFixed(3)}`
          if (!coordMap.has(key)) {
            const coordObj = { lat: cp.latitude, lon: cp.longitude, key }
            coordMap.set(key, coordList.length)
            coordList.push(coordObj)
          }
        }
      }
    }

    if (coordList.length === 0) {
      return routesData
    }

    // 2. Fetch from Open-Meteo in chunks of up to 25 coordinates
    const MAX_CHUNK = 25
    const forecastResults = []

    for (let i = 0; i < coordList.length; i += MAX_CHUNK) {
      const chunk = coordList.slice(i, i + MAX_CHUNK)
      const lats = chunk.map((c) => c.lat.toFixed(4)).join(',')
      const lons = chunk.map((c) => c.lon.toFixed(4)).join(',')

      const url =
        `https://api.open-meteo.com/v1/forecast?latitude=${lats}&longitude=${lons}` +
        `&hourly=temperature_2m,wind_speed_10m,wind_gusts_10m,precipitation,snowfall,weather_code,precipitation_probability` +
        `&wind_speed_unit=mph&precipitation_unit=inch&temperature_unit=fahrenheit&timezone=UTC`

      const res = await fetch(url)
      if (!res.ok) {
        return routesData // If Open-Meteo fails, return original data safely
      }

      const json = await res.json()
      if (Array.isArray(json)) {
        forecastResults.push(...json)
      } else if (json && typeof json === 'object') {
        forecastResults.push(...Array(chunk.length).fill(json))
      }
    }

    if (forecastResults.length === 0) {
      return routesData
    }

    // 3. Enrich each checkpoint with real-time weather & 48-hour hourly forecast
    const severityOrder = ['no_travel', 'severe', 'high', 'moderate', 'low']
    const scoreMap = { low: 10, moderate: 35, high: 60, severe: 80, no_travel: 100, unknown: null }

    for (const route of routesData.routes) {
      let routeSevereMiles = 0
      let routeHighMiles = 0
      let routeModerateMiles = 0
      let routeLowMiles = 0
      let routeNoTravelMiles = 0
      let scoreSum = 0
      let scoredDistance = 0

      for (let idx = 0; idx < (route.checkpoints || []).length; idx++) {
        const cp = route.checkpoints[idx]
        const key = `${cp.latitude.toFixed(3)},${cp.longitude.toFixed(3)}`
        const forecastIdx = coordMap.get(key)
        const forecast = forecastResults[forecastIdx]

        if (!forecast || !forecast.hourly || !Array.isArray(forecast.hourly.time)) {
          continue
        }

        const hourly = forecast.hourly
        const arrivalIso = cp.estimated_arrival || new Date().toISOString()
        const arrivalDt = new Date(arrivalIso).getTime()

        // Find closest hour slot for arrival
        let bestSlotIdx = 0
        let minDiff = Infinity
        const timeStrs = hourly.time

        for (let s = 0; s < timeStrs.length; s++) {
          const slotDt = new Date(timeStrs[s]).getTime()
          const diff = Math.abs(slotDt - arrivalDt)
          if (diff < minDiff) {
            minDiff = diff
            bestSlotIdx = s
          }
        }

        const windSpeed = hourly.wind_speed_10m?.[bestSlotIdx] ?? 0
        const windGust = hourly.wind_gusts_10m?.[bestSlotIdx] ?? 0
        const precipRate = hourly.precipitation?.[bestSlotIdx] ?? 0
        const snowRate = hourly.snowfall?.[bestSlotIdx] ?? 0
        const temp = hourly.temperature_2m?.[bestSlotIdx] ?? null
        const wcode = hourly.weather_code?.[bestSlotIdx] ?? 0
        const pprob = hourly.precipitation_probability?.[bestSlotIdx] ?? 0

        // Calculate risk
        const windCat = evaluateWindCategory(windSpeed, loadWeightLb)
        const precipCat = evaluatePrecipitationCategory(precipRate)
        const snowCat = evaluateSnowfallCategory(snowRate)
        const highestCat = severityOrder.find((c) => c === windCat || c === precipCat || c === snowCat) || 'low'

        cp.risk_level = highestCat
        cp.risk_score = scoreMap[highestCat]

        cp.weather = {
          timestamp: arrivalIso,
          forecast_timestamp: timeStrs[bestSlotIdx] || arrivalIso,
          data_availability: 'available',
          temperature: temp,
          condition: WMO_WEATHER_CODES[wcode] || 'Fair',
          weather_code: wcode,
          wind_speed_mph: windSpeed,
          wind_gust_mph: windGust,
          precipitation_probability: pprob,
          precipitation_in_per_hour: precipRate,
          snowfall_in_per_hour: snowRate,
          precipitation_rate_in_per_hour: precipRate,
          snowfall_rate_in_per_hour: snowRate,
          precipitation_accumulation_in: precipRate,
          snowfall_accumulation_in: snowRate,
          visibility_miles: null,
          notes: 'Live forecast enriched via direct Open-Meteo client connection.',
          limitations: ['Hourly precipitation and snowfall represent 1-hour average rates derived from forecasts.'],
          units: {
            temperature: '°F',
            wind_speed: 'mph',
            wind_gust: 'mph',
            precipitation: 'in/h',
            snowfall: 'in/h',
            precipitation_probability: '%',
            visibility: 'miles',
          },
        }

        // Build 48-hour hourly series for timeline slider
        const hourlySeries = []
        const baseStart = new Date(arrivalIso)
        baseStart.setMinutes(0, 0, 0)

        for (let h = 0; h <= 48; h++) {
          const targetSlotTime = new Date(baseStart.getTime() + h * 3600 * 1000).getTime()
          let hSlotIdx = -1
          let hMinDiff = Infinity

          for (let s = 0; s < timeStrs.length; s++) {
            const sDt = new Date(timeStrs[s]).getTime()
            const diff = Math.abs(sDt - targetSlotTime)
            if (diff < hMinDiff && diff <= 3600 * 1000) {
              hMinDiff = diff
              hSlotIdx = s
            }
          }

          if (hSlotIdx >= 0) {
            const hWind = hourly.wind_speed_10m?.[hSlotIdx] ?? 0
            const hGust = hourly.wind_gusts_10m?.[hSlotIdx] ?? 0
            const hPrecip = hourly.precipitation?.[hSlotIdx] ?? 0
            const hSnow = hourly.snowfall?.[hSlotIdx] ?? 0
            const hWcode = hourly.weather_code?.[hSlotIdx] ?? 0

            const hWindCat = evaluateWindCategory(hWind, loadWeightLb)
            const hPrecipCat = evaluatePrecipitationCategory(hPrecip)
            const hSnowCat = evaluateSnowfallCategory(hSnow)
            const hRiskCat = severityOrder.find((c) => c === hWindCat || c === hPrecipCat || c === hSnowCat) || 'low'

            hourlySeries.push({
              forecast_timestamp: timeStrs[hSlotIdx],
              hour_offset: h,
              temperature: hourly.temperature_2m?.[hSlotIdx] ?? null,
              condition: WMO_WEATHER_CODES[hWcode] || 'Fair',
              weather_code: hWcode,
              wind_speed_mph: hWind,
              wind_gust_mph: hGust,
              precipitation_in_per_hour: hPrecip,
              snowfall_in_per_hour: hSnow,
              precipitation_rate_in_per_hour: hPrecip,
              snowfall_rate_in_per_hour: hSnow,
              precipitation_probability: hourly.precipitation_probability?.[hSlotIdx] ?? 0,
              risk_level: hRiskCat,
            })
          }
        }

        cp.hourly_forecast = hourlySeries

        // Compute segment miles
        const prevCp = idx > 0 ? route.checkpoints[idx - 1] : null
        const nextCp = idx < route.checkpoints.length - 1 ? route.checkpoints[idx + 1] : null
        let segMiles = 25.0
        if (cp.distance_from_origin_miles != null) {
          const dPrev = prevCp ? cp.distance_from_origin_miles - prevCp.distance_from_origin_miles : 0
          const dNext = nextCp ? nextCp.distance_from_origin_miles - cp.distance_from_origin_miles : 0
          segMiles = Math.max(1, (dPrev + dNext) / 2)
        }

        if (highestCat === 'no_travel') routeNoTravelMiles += segMiles
        else if (highestCat === 'severe') routeSevereMiles += segMiles
        else if (highestCat === 'high') routeHighMiles += segMiles
        else if (highestCat === 'moderate') routeModerateMiles += segMiles
        else routeLowMiles += segMiles

        if (cp.risk_score != null) {
          scoreSum += cp.risk_score * segMiles
          scoredDistance += segMiles
        }
      }

      // Update route-level risk assessment
      const avgScore = scoredDistance > 0 ? Math.round((scoreSum / scoredDistance) * 10) / 10 : 15.0

      route.risk_assessment = {
        ...route.risk_assessment,
        overall_risk_level:
          routeNoTravelMiles > 0
            ? 'no_travel'
            : routeSevereMiles > 0
              ? 'severe'
              : routeHighMiles > 0
                ? 'high'
                : routeModerateMiles > 0
                  ? 'moderate'
                  : 'low',
        risk_score: avgScore,
        low_risk_miles: Math.round(routeLowMiles * 10) / 10,
        moderate_risk_miles: Math.round(routeModerateMiles * 10) / 10,
        high_risk_miles: Math.round(routeHighMiles * 10) / 10,
        severe_risk_miles: Math.round(routeSevereMiles * 10) / 10,
        no_travel_miles: Math.round(routeNoTravelMiles * 10) / 10,
        unknown_risk_miles: 0,
        data_quality: 'available',
      }

      route.weather_summary = {
        ...route.weather_summary,
        total_checkpoints: route.checkpoints.length,
        available_checkpoints: route.checkpoints.length,
        provider: 'Open-Meteo Forecast API (Direct Client Connection)',
      }

      if (route.recommendation) {
        route.recommendation.assessment_status = 'complete'
        route.recommendation.eligibility = routeNoTravelMiles > 0 ? 'ineligible_no_travel' : 'eligible'
      }
    }

    // 4. Update recommendation summary
    if (routesData.recommendation_summary) {
      routesData.recommendation_summary.incomplete_data_warning = false
      const topRoute = routesData.routes[0]
      routesData.recommendation_summary.recommended_route_id = topRoute?.route_id || null
      routesData.recommendation_summary.executive_summary = `Live weather analysis complete for all ${routesData.routes.length} route options. Recommended route: ${topRoute?.display_name || 'Primary Corridor'}.`
      if (topRoute?.recommendation) {
        topRoute.recommendation.is_recommended = true
      }
    }

    return routesData
  } catch (err) {
    console.warn('Client-side weather enrichment failed, falling back to server response:', err)
    return routesData
  }
}
