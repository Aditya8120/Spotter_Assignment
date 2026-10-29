/**
 * Frontend API Service Module
 * Handles request payload serialization, HTTP networking to the Django backend,
 * error normalization, and response parsing for route planning and system health.
 */

// Read base URL from Vite environment variable or fall back to local Django development port
export const API_BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env && import.meta.env.VITE_API_BASE_URL) ||
  'http://localhost:8000'

/**
 * Custom error class normalizing API, validation, network, and configuration failures.
 */
export class ApiError extends Error {
  constructor({ message, status = 0, code = 'unknown_error', fieldErrors = {}, details = null }) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.fieldErrors = fieldErrors
    this.details = details
    this.isNotConfigured = status === 503 || code === 'provider_not_configured'
    this.isNetworkError = status === 0 || code === 'network_error'
    this.isValidationError = status === 400 || code === 'validation_error'
  }
}

/**
 * Builds and normalizes the route planning request payload matching the Django backend contract.
 *
 * Backend expects:
 * - origin: string (city or "lat,lon")
 * - destination: string (city or "lat,lon")
 * - departure_datetime: ISO 8601 string
 * - load_weight_lb: float > 0
 * - checkpoint_interval_miles: integer in [10, 25, 50]
 */
export function buildRoutePlanPayload(formData) {
  if (!formData || typeof formData !== 'object') {
    throw new Error('Form data must be an object.')
  }

  const { origin, destination, departureDatetime, loadWeightLb, checkpointIntervalMiles } = formData

  // Clean strings
  const cleanOrigin = (origin || '').trim()
  const cleanDestination = (destination || '').trim()

  // Format departure datetime into full ISO 8601 format
  let isoDatetime = ''
  if (departureDatetime) {
    const dt = new Date(departureDatetime)
    if (isNaN(dt.getTime())) {
      throw new Error('Invalid departure date and time.')
    }
    isoDatetime = dt.toISOString()
  }

  // Parse numeric weight
  const weight = parseFloat(loadWeightLb)
  if (isNaN(weight) || weight <= 0) {
    throw new Error('Load weight must be a positive number greater than 0.')
  }

  // Parse interval
  const interval = parseInt(checkpointIntervalMiles, 10) || 25

  return {
    origin: cleanOrigin,
    destination: cleanDestination,
    departure_datetime: isoDatetime,
    load_weight_lb: weight,
    checkpoint_interval_miles: interval,
  }
}

/**
 * Dispatches route planning request to POST /api/routes/
 *
 * @param {Object} formData Form inputs from the UI.
 * @param {Object} options Optional fetch configuration (baseUrl, signal, timeoutMs).
 * @returns {Promise<Object>} Backend response payload containing routes and recommendations.
 */
export async function planRoutes(formData, options = {}) {
  const baseUrl = options.baseUrl || API_BASE_URL
  const endpoint = `${baseUrl.replace(/\/+$/, '')}/api/routes/`

  let payload
  try {
    payload = buildRoutePlanPayload(formData)
  } catch (err) {
    throw new ApiError({
      message: err.message || 'Invalid form inputs.',
      status: 400,
      code: 'client_validation_error',
    })
  }

  // Timeout controller (default 30 seconds for external routing/weather fetch)
  const timeoutMs = options.timeoutMs || 30000
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify(payload),
      signal: options.signal || controller.signal,
    })

    clearTimeout(timeoutId)

    let responseData
    try {
      responseData = await response.json()
    } catch {
      responseData = null
    }

    // Success response
    if (response.ok) {
      return responseData
    }

    // -----------------------------------------------------------------------
    // Structured Backend Error Handling
    // -----------------------------------------------------------------------
    const status = response.status
    const code = responseData?.code || 'api_error'
    let message = responseData?.message

    // Case 1: Provider Not Configured (HTTP 503)
    // Mapbox credentials are not yet set in backend environment
    if (status === 503 || code === 'provider_not_configured') {
      message =
        'Backend Setup Pending: The routing service is not yet configured with a Mapbox access token (MAPBOX_ACCESS_TOKEN). ' +
        'Add your token to the backend .env file to enable live route calculations.'
      return {
        _isPendingSetup: true,
        status: 'setup_pending',
        code: 'provider_not_configured',
        message,
      }
    }

    // Case 2: Validation Errors (HTTP 400)
    const fieldErrors = {}
    if (status === 400) {
      if (responseData && typeof responseData === 'object') {
        for (const [key, val] of Object.entries(responseData)) {
          if (Array.isArray(val)) {
            fieldErrors[key] = val.join(' ')
          } else if (typeof val === 'string') {
            fieldErrors[key] = val
          }
        }
      }
      if (!message) {
        const errorList = Object.entries(fieldErrors).map(([f, msg]) => `${f}: ${msg}`)
        message = errorList.length > 0 ? errorList.join(' | ') : 'Validation failed. Please verify your inputs.'
      }
    }

    // Case 3: No Route Found (HTTP 404)
    if (status === 404) {
      message = message || 'No driving route could be found between the specified origin and destination.'
    }

    // Case 4: Rate Limit Reached (HTTP 429)
    if (status === 429) {
      message = message || 'Routing provider rate limit reached. Please wait a moment and try again.'
    }

    // Case 5: Provider Gateway Timeout / Service Error (HTTP 502 / 504)
    if (status === 502 || status === 504) {
      message = message || 'External routing or weather provider is temporarily unavailable. Please retry.'
    }

    // Case 6: Internal Error (HTTP 500)
    if (status >= 500) {
      message = message || 'An internal server error occurred while calculating routes.'
    }

    throw new ApiError({
      message: message || `Request failed with status ${status}.`,
      status,
      code,
      fieldErrors,
      details: responseData,
    })
  } catch (err) {
    clearTimeout(timeoutId)

    if (err instanceof ApiError) {
      throw err
    }

    // Abort / Timeout error
    if (err.name === 'AbortError') {
      throw new ApiError({
        message: 'Request timed out. The routing server took too long to respond.',
        status: 504,
        code: 'client_timeout',
      })
    }

    // Network / Connection Error (e.g., Django server not running or CORS blocked)
    throw new ApiError({
      message: `Unable to connect to the backend API at ${baseUrl}. Ensure the Django backend server is running on http://localhost:8000.`,
      status: 0,
      code: 'network_error',
    })
  }
}

/**
 * Checks system health via GET /api/health/
 */
export async function checkHealth(options = {}) {
  const baseUrl = options.baseUrl || API_BASE_URL
  const endpoint = `${baseUrl.replace(/\/+$/, '')}/api/health/`

  try {
    const res = await fetch(endpoint, {
      headers: { Accept: 'application/json' },
      signal: options.signal,
    })
    if (!res.ok) {
      throw new Error(`Health check returned status ${res.status}`)
    }
    return await res.json()
  } catch (err) {
    throw new ApiError({
      message: `Backend health check failed: ${err.message}`,
      status: 0,
      code: 'health_check_failed',
    })
  }
}
