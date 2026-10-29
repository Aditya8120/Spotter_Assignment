import React from 'react'
import { WEATHER_LAYERS } from '../utils/weatherLayers'

export function WeatherLayerSelector({ activeLayer = 'risk', onSelectLayer }) {
  return (
    <div className="weather-layer-selector" role="toolbar" aria-label="Weather Overlay Layer Options">
      <div className="layer-selector-label">
        <span className="selector-caption">Weather Layer:</span>
      </div>
      <div className="layer-button-group" role="radiogroup">
        {Object.values(WEATHER_LAYERS).map((layer) => {
          const isActive = activeLayer === layer.key
          return (
            <button
              key={layer.key}
              type="button"
              role="radio"
              aria-checked={isActive}
              className={`layer-btn ${isActive ? 'active' : ''}`}
              onClick={() => onSelectLayer && onSelectLayer(layer.key)}
              title={layer.description}
            >
              <span className="layer-icon" aria-hidden="true">{layer.icon}</span>
              <span className="layer-title">{layer.label}</span>
              <span className="layer-unit">({layer.unit})</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
