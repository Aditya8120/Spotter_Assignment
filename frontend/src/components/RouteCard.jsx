import React from 'react'

export function RouteCard({ route, isSelected, onSelect }) {
  const {
    route_id,
    display_name,
    rank,
    distance_miles,
    distance_km,
    duration_formatted,
    risk_assessment,
    recommendation,
  } = route

  const isRecommended = recommendation?.is_recommended
  const isNoTravel = risk_assessment?.no_travel_warning || risk_assessment?.overall_risk_level === 'no_travel'
  const isSevere = risk_assessment?.overall_risk_level === 'severe'
  const isHigh = risk_assessment?.overall_risk_level === 'high'

  const getRankBadgeClass = () => {
    if (isRecommended) return 'badge-recommended'
    if (isNoTravel) return 'badge-no-travel'
    if (isSevere) return 'badge-severe'
    if (isHigh) return 'badge-high'
    return 'badge-viable'
  }

  const getRiskLevelBadge = () => {
    const lvl = risk_assessment?.overall_risk_level || 'unknown'
    switch (lvl) {
      case 'low':
        return <span className="risk-tag risk-low">Low Risk</span>
      case 'moderate':
        return <span className="risk-tag risk-mod">Moderate Risk</span>
      case 'high':
        return <span className="risk-tag risk-high">High Risk</span>
      case 'severe':
        return <span className="risk-tag risk-sev">Severe Risk</span>
      case 'no_travel':
        return <span className="risk-tag risk-notravel">No Travel</span>
      default:
        return <span className="risk-tag risk-unk">Unknown</span>
    }
  }

  return (
    <article
      className={`card route-card ${isRecommended ? 'is-recommended' : ''} ${isSelected ? 'is-selected' : ''}`}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          if (onSelect) {
            onSelect()
          }
        }
      }}
      aria-label={`${display_name}, Rank ${rank}`}
    >
      <div className="route-card-header">
        <div className="route-title-meta">
          <span className="route-rank-number">#{rank}</span>
          <div>
            <h3 className="route-name">{display_name}</h3>
            <span className="route-id-tag">{route_id} &bull; Mapbox &amp; Weather Assessed</span>
          </div>
        </div>
        <span className={`badge ${getRankBadgeClass()}`}>
          {isRecommended ? '★ Recommended' : recommendation?.status === 'viable_alternative' ? 'Viable Alternative' : 'Not Recommended'}
        </span>
      </div>

      {/* Metrics Row */}
      <div className="route-metrics-grid">
        <div className="metric-box">
          <span className="metric-label">Distance</span>
          <span className="metric-value">{distance_miles != null ? distance_miles.toFixed(1) : 'N/A'} mi</span>
          <span className="metric-sub">{distance_km != null ? `${distance_km.toFixed(1)} km` : ''}</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Drive Time</span>
          <span className="metric-value">{duration_formatted || 'N/A'}</span>
          <span className="metric-sub">Est. Duration</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Severe Miles</span>
          <span className={`metric-value ${risk_assessment?.severe_risk_miles > 0 ? 'text-danger' : 'text-safe'}`}>
            {risk_assessment?.severe_risk_miles != null ? `${risk_assessment.severe_risk_miles.toFixed(1)} mi` : '0.0 mi'}
          </span>
          <span className="metric-sub">Priority 1 Metric</span>
        </div>

        <div className="metric-box">
          <span className="metric-label">Avg Risk Score</span>
          <span className="metric-value">{risk_assessment?.risk_score != null ? risk_assessment.risk_score.toFixed(1) : 'N/A'}</span>
          <span className="metric-sub">0–100 Scale</span>
        </div>
      </div>

      {/* Hazard Mileage Breakdown */}
      <div className="hazard-breakdown-strip">
        <div className="breakdown-item">
          <span className="color-dot dot-low"></span>
          <span>Low: {risk_assessment?.low_risk_miles != null ? risk_assessment.low_risk_miles.toFixed(1) : 0} mi</span>
        </div>
        <div className="breakdown-item">
          <span className="color-dot dot-mod"></span>
          <span>Mod: {risk_assessment?.moderate_risk_miles != null ? risk_assessment.moderate_risk_miles.toFixed(1) : 0} mi</span>
        </div>
        <div className="breakdown-item">
          <span className="color-dot dot-high"></span>
          <span>High: {risk_assessment?.high_risk_miles != null ? risk_assessment.high_risk_miles.toFixed(1) : 0} mi</span>
        </div>
        <div className="breakdown-item">
          <span className="color-dot dot-sev"></span>
          <span>Sev: {risk_assessment?.severe_risk_miles != null ? risk_assessment.severe_risk_miles.toFixed(1) : 0} mi</span>
        </div>
        {risk_assessment?.no_travel_miles > 0 && (
          <div className="breakdown-item text-danger">
            <span className="color-dot dot-notravel"></span>
            <span>No Travel: {risk_assessment.no_travel_miles.toFixed(1)} mi</span>
          </div>
        )}
      </div>

      {/* Recommendation Explanation */}
      <div className="route-explanation-box">
        <div className="explanation-header">
          {getRiskLevelBadge()}
          <span className="explanation-title">Recommendation Rationale:</span>
        </div>
        <p className="explanation-text">{recommendation?.explanation || 'No explanation provided.'}</p>
      </div>
    </article>
  )
}
