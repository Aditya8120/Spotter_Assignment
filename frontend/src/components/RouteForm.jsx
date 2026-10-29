import React, { useState } from 'react'

const QUICK_PRESETS = [
  {
    label: 'Chicago → Dallas (45k lb)',
    origin: 'Chicago, IL',
    destination: 'Dallas, TX',
    load_weight_lb: 45000,
    interval: 25,
  },
  {
    label: 'Denver → Salt Lake (35k lb)',
    origin: 'Denver, CO',
    destination: 'Salt Lake City, UT',
    load_weight_lb: 35000,
    interval: 25,
  },
  {
    label: 'Seattle → Spokane (18k lb)',
    origin: 'Seattle, WA',
    destination: 'Spokane, WA',
    load_weight_lb: 18000,
    interval: 10,
  },
]

// Helper for tomorrow at 08:00 AM local time
function getDefaultDateTime() {
  const tomorrow = new Date()
  tomorrow.setDate(tomorrow.getDate() + 1)
  tomorrow.setHours(8, 0, 0, 0)
  const tzOffset = tomorrow.getTimezoneOffset() * 60000
  return new Date(tomorrow.getTime() - tzOffset).toISOString().slice(0, 16)
}

export function RouteForm({ onSubmit, isLoading = false, serverFieldErrors = {}, initialValues = {} }) {
  const [origin, setOrigin] = useState(initialValues.origin || 'Chicago, IL')
  const [destination, setDestination] = useState(initialValues.destination || 'Dallas, TX')
  const [departureDatetime, setDepartureDatetime] = useState(initialValues.departureDatetime || getDefaultDateTime)
  const [loadWeightLb, setLoadWeightLb] = useState((initialValues.loadWeightLb || 45000).toString())
  const [checkpointInterval, setCheckpointInterval] = useState(initialValues.checkpointIntervalMiles || 25)
  const [errors, setErrors] = useState({})
  const [touched, setTouched] = useState({})

  const validate = () => {
    const errs = {}

    // Origin
    if (!origin || !origin.trim()) {
      errs.origin = 'Origin location is required (e.g. city name or coordinates).'
    }

    // Destination
    if (!destination || !destination.trim()) {
      errs.destination = 'Destination location is required.'
    } else if (origin && origin.trim().toLowerCase() === destination.trim().toLowerCase()) {
      errs.destination = 'Destination cannot be identical to origin.'
    }

    // Departure Datetime
    if (!departureDatetime) {
      errs.departureDatetime = 'Departure date and time are required.'
    } else {
      const dt = new Date(departureDatetime)
      if (isNaN(dt.getTime())) {
        errs.departureDatetime = 'Please provide a valid date and time.'
      }
    }

    // Load Weight
    if (!loadWeightLb || loadWeightLb.toString().trim() === '') {
      errs.loadWeightLb = 'Truck load weight is required.'
    } else {
      const weight = parseFloat(loadWeightLb)
      if (isNaN(weight) || weight <= 0) {
        errs.loadWeightLb = 'Load weight must be a positive number greater than 0 lb.'
      } else if (weight > 250000) {
        errs.loadWeightLb = 'Load weight exceeds maximum realistic limit of 250,000 lb.'
      }
    }

    // Checkpoint Interval
    if (![10, 25, 50].includes(Number(checkpointInterval))) {
      errs.checkpointInterval = 'Sampling interval must be 10, 25, or 50 miles.'
    }

    return errs
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (isLoading) return

    const validationErrors = validate()
    setErrors(validationErrors)
    setTouched({
      origin: true,
      destination: true,
      departureDatetime: true,
      loadWeightLb: true,
      checkpointInterval: true,
    })

    if (Object.keys(validationErrors).length === 0) {
      onSubmit({
        origin: origin.trim(),
        destination: destination.trim(),
        departureDatetime,
        loadWeightLb: parseFloat(loadWeightLb),
        checkpointIntervalMiles: Number(checkpointInterval),
      })
    }
  }

  const handleApplyPreset = (preset) => {
    setOrigin(preset.origin)
    setDestination(preset.destination)
    setLoadWeightLb(preset.load_weight_lb.toString())
    setCheckpointInterval(preset.interval)
    setErrors({})
  }

  const getFieldError = (field) => {
    if (touched[field] && errors[field]) return errors[field]
    if (serverFieldErrors[field]) return serverFieldErrors[field]
    return null
  }

  return (
    <div className="card route-form-card">
      <div className="card-header">
        <div className="card-title-group">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
          </svg>
          <h2 className="card-title">Route Planning Parameters</h2>
        </div>
        <span className="badge badge-subtle">Logistics Dispatch</span>
      </div>

      <div className="preset-strip">
        <span className="preset-label">Quick Presets:</span>
        <div className="preset-buttons">
          {QUICK_PRESETS.map((p, idx) => (
            <button
              key={idx}
              type="button"
              disabled={isLoading}
              className="btn-preset"
              onClick={() => handleApplyPreset(p)}
              title={`Load ${p.origin} to ${p.destination}`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <form onSubmit={handleSubmit} noValidate className="form-body">
        {/* Origin */}
        <div className={`form-group ${getFieldError('origin') ? 'has-error' : ''}`}>
          <label htmlFor="origin" className="form-label">
            Origin Location <span className="required-star">*</span>
          </label>
          <div className="input-wrapper">
            <span className="input-icon" aria-hidden="true">📍</span>
            <input
              id="origin"
              type="text"
              disabled={isLoading}
              className="form-input"
              placeholder="e.g. Chicago, IL or 41.8781, -87.6298"
              value={origin}
              onChange={(e) => {
                setOrigin(e.target.value)
                if (touched.origin) setErrors({ ...errors, origin: undefined })
              }}
              onBlur={() => setTouched({ ...touched, origin: true })}
              required
            />
          </div>
          {getFieldError('origin') && (
            <p className="field-error" role="alert">{getFieldError('origin')}</p>
          )}
        </div>

        {/* Destination */}
        <div className={`form-group ${getFieldError('destination') ? 'has-error' : ''}`}>
          <label htmlFor="destination" className="form-label">
            Destination Location <span className="required-star">*</span>
          </label>
          <div className="input-wrapper">
            <span className="input-icon" aria-hidden="true">🏁</span>
            <input
              id="destination"
              type="text"
              disabled={isLoading}
              className="form-input"
              placeholder="e.g. Dallas, TX or 32.7767, -96.7970"
              value={destination}
              onChange={(e) => {
                setDestination(e.target.value)
                if (touched.destination) setErrors({ ...errors, destination: undefined })
              }}
              onBlur={() => setTouched({ ...touched, destination: true })}
              required
            />
          </div>
          {getFieldError('destination') && (
            <p className="field-error" role="alert">{getFieldError('destination')}</p>
          )}
        </div>

        {/* Departure Date and Time */}
        <div className={`form-group ${getFieldError('departure_datetime') || getFieldError('departureDatetime') ? 'has-error' : ''}`}>
          <label htmlFor="departureDatetime" className="form-label">
            Departure Date & Time (Local) <span className="required-star">*</span>
          </label>
          <div className="input-wrapper">
            <span className="input-icon" aria-hidden="true">🕒</span>
            <input
              id="departureDatetime"
              type="datetime-local"
              disabled={isLoading}
              className="form-input"
              value={departureDatetime}
              onChange={(e) => {
                setDepartureDatetime(e.target.value)
                if (touched.departureDatetime) setErrors({ ...errors, departureDatetime: undefined })
              }}
              onBlur={() => setTouched({ ...touched, departureDatetime: true })}
              required
            />
          </div>
          {(getFieldError('departure_datetime') || getFieldError('departureDatetime')) && (
            <p className="field-error" role="alert">{getFieldError('departure_datetime') || getFieldError('departureDatetime')}</p>
          )}
          <span className="form-helper">Weather is evaluated at each checkpoint's estimated arrival time.</span>
        </div>

        {/* Truck Load Weight */}
        <div className={`form-group ${getFieldError('load_weight_lb') || getFieldError('loadWeightLb') ? 'has-error' : ''}`}>
          <div className="label-with-weight-tier">
            <label htmlFor="loadWeightLb" className="form-label">
              Load Weight (Pounds) <span className="required-star">*</span>
            </label>
            {parseFloat(loadWeightLb) > 40000 ? (
              <span className="badge badge-severe-tier">Very Heavy (&gt; 40k lb)</span>
            ) : parseFloat(loadWeightLb) > 30000 ? (
              <span className="badge badge-heavy-tier">Heavy (&gt; 30k lb)</span>
            ) : (
              <span className="badge badge-normal-tier">Standard (&le; 30k lb)</span>
            )}
          </div>
          <div className="input-wrapper">
            <span className="input-icon" aria-hidden="true">⚖️</span>
            <input
              id="loadWeightLb"
              type="number"
              step="500"
              min="1"
              max="250000"
              disabled={isLoading}
              className="form-input"
              placeholder="e.g. 45000"
              value={loadWeightLb}
              onChange={(e) => {
                setLoadWeightLb(e.target.value)
                if (touched.loadWeightLb) setErrors({ ...errors, loadWeightLb: undefined })
              }}
              onBlur={() => setTouched({ ...touched, loadWeightLb: true })}
              required
            />
            <span className="input-suffix">lb</span>
          </div>
          {(getFieldError('load_weight_lb') || getFieldError('loadWeightLb')) && (
            <p className="field-error" role="alert">{getFieldError('load_weight_lb') || getFieldError('loadWeightLb')}</p>
          )}
          <span className="form-helper">
            {parseFloat(loadWeightLb) > 40000
              ? 'Active load rule: Wind 35–44 mph elevates to Severe risk; 45+ mph triggers No Travel.'
              : parseFloat(loadWeightLb) > 30000
              ? 'Active load rule: Wind 45–54 mph triggers No Travel advisory.'
              : 'Standard load rules: Wind 55+ mph triggers No Travel.'}
          </span>
        </div>

        {/* Checkpoint Sampling Interval */}
        <div className="form-group">
          <label className="form-label">
            Checkpoint Weather Sampling Interval
          </label>
          <div className="segmented-control" role="radiogroup" aria-label="Checkpoint Sampling Interval">
            {[10, 25, 50].map((interval) => (
              <label
                key={interval}
                className={`segmented-option ${Number(checkpointInterval) === interval ? 'selected' : ''} ${isLoading ? 'disabled' : ''}`}
              >
                <input
                  type="radio"
                  name="checkpointInterval"
                  value={interval}
                  disabled={isLoading}
                  checked={Number(checkpointInterval) === interval}
                  onChange={() => setCheckpointInterval(interval)}
                />
                <span>{interval} miles {interval === 25 ? '(Default)' : ''}</span>
              </label>
            ))}
          </div>
          <span className="form-helper">Controls resolution of weather checkpoints along the driving path.</span>
        </div>

        {/* Action Button */}
        <button
          type="submit"
          disabled={isLoading}
          className="btn-primary btn-block btn-lg"
          id="find-routes-btn"
        >
          {isLoading ? (
            <>
              <span className="btn-spinner" aria-hidden="true"></span>
              <span>Calculating Routes &amp; Weather...</span>
            </>
          ) : (
            <>
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <span>Find Routes &amp; Analyze Weather</span>
            </>
          )}
        </button>
      </form>
    </div>
  )
}
