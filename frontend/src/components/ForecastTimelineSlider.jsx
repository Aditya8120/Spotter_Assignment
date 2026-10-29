import React, { useEffect, useState } from 'react'

export function ForecastTimelineSlider({
  slots = [],
  selectedHour = 0,
  onSelectHour,
  isSlotAvailable = true,
  availabilityMessage = '',
}) {
  const [isPlaying, setIsPlaying] = useState(false)

  const activeSlot = slots[selectedHour] || slots[0] || {
    hourOffset: 0,
    label: 'Departure (T+0h)',
    displayTime: '08:00',
    displayDate: 'Today',
  }

  // Play / Pause auto-advance timer
  useEffect(() => {
    let timer = null
    if (isPlaying) {
      timer = setInterval(() => {
        onSelectHour((prev) => {
          if (prev >= slots.length - 1) {
            setIsPlaying(false)
            return 0
          }
          return prev + 1
        })
      }, 1200)
    }
    return () => {
      if (timer) clearInterval(timer)
    }
  }, [isPlaying, slots.length, onSelectHour])

  const handleSliderChange = (e) => {
    const val = parseInt(e.target.value, 10)
    if (!isNaN(val)) {
      setIsPlaying(false)
      onSelectHour(val)
    }
  }

  const handleStep = (delta) => {
    setIsPlaying(false)
    const next = Math.max(0, Math.min(slots.length - 1, selectedHour + delta))
    onSelectHour(next)
  }

  const handleJump = (hour) => {
    setIsPlaying(false)
    const next = Math.max(0, Math.min(slots.length - 1, hour))
    onSelectHour(next)
  }

  return (
    <div className="forecast-timeline-panel" role="region" aria-label="Forecast Timeline Controls (0 to 48 Hours)">
      <div className="timeline-header-bar">
        <div className="timeline-title-group">
          <span className="timeline-icon" aria-hidden="true">⏱️</span>
          <span className="timeline-heading">Forecast Horizon: 0–48 Hours</span>
        </div>

        <div className="timeline-readout-card">
          <span className="readout-label">Selected Horizon:</span>
          <span className="readout-value">
            <strong>{activeSlot.label}</strong> &bull; {activeSlot.displayDate} at {activeSlot.displayTime}
          </span>
          <span className={`readout-availability-tag ${isSlotAvailable ? 'tag-available' : 'tag-unavailable'}`}>
            {isSlotAvailable ? '● Weather Available' : '⚠️ Horizon Slot Unavailable'}
          </span>
        </div>
      </div>

      {/* Slider Row */}
      <div className="timeline-controls-row">
        <div className="timeline-playback-btns">
          <button
            type="button"
            className="btn-playback-step"
            onClick={() => handleStep(-1)}
            disabled={selectedHour <= 0}
            title="Step Back 1 Hour"
            aria-label="Previous Hour"
          >
            &minus;1h
          </button>
          <button
            type="button"
            className={`btn-playback-play ${isPlaying ? 'is-playing' : ''}`}
            onClick={() => setIsPlaying((prev) => !prev)}
            title={isPlaying ? 'Pause Timeline' : 'Play Timeline Animation (48h)'}
            aria-label={isPlaying ? 'Pause Timeline' : 'Play Timeline'}
          >
            {isPlaying ? '⏸ Pause' : '▶ Play'}
          </button>
          <button
            type="button"
            className="btn-playback-step"
            onClick={() => handleStep(1)}
            disabled={selectedHour >= slots.length - 1}
            title="Step Forward 1 Hour"
            aria-label="Next Hour"
          >
            +1h
          </button>
        </div>

        {/* Range Track */}
        <div className="slider-track-container">
          <input
            type="range"
            min="0"
            max={slots.length > 0 ? slots.length - 1 : 48}
            step="1"
            value={selectedHour}
            onChange={handleSliderChange}
            className="timeline-slider-input"
            aria-valuemin="0"
            aria-valuemax="48"
            aria-valuenow={selectedHour}
            aria-label="Forecast hour slider from 0 to 48 hours"
          />
          <div className="slider-tick-labels" aria-hidden="true">
            <span>T+0h (Departure)</span>
            <span>+12h</span>
            <span>+24h</span>
            <span>+36h</span>
            <span>+48h</span>
          </div>
        </div>

        {/* Quick Jump Buttons */}
        <div className="timeline-quick-jumps" role="group" aria-label="Quick jump to forecast hours">
          {[0, 6, 12, 24, 48].map((h) => (
            <button
              key={h}
              type="button"
              className={`btn-quick-jump ${selectedHour === h ? 'active' : ''}`}
              onClick={() => handleJump(h)}
            >
              {h === 0 ? 'T+0h' : `+${h}h`}
            </button>
          ))}
        </div>
      </div>

      {/* Availability Guidance Banner */}
      {!isSlotAvailable && (
        <div className="timeline-availability-notice" role="alert">
          <span className="notice-icon">⚠️</span>
          <span>{availabilityMessage || 'No forecast data is recorded for the selected time slot. Checkpoints reflect weather sampled at their scheduled arrival times.'}</span>
        </div>
      )}
    </div>
  )
}
