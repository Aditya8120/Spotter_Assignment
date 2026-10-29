import React, { useState } from 'react'
import { Header } from './components/Header'
import { RouteForm } from './components/RouteForm'
import { MapPlaceholder } from './components/MapPlaceholder'
import { RouteResults } from './components/RouteResults'
import { RiskThresholdReference } from './components/RiskThresholdReference'
import './App.css'

const DEMO_ROUTE_OPTIONS = [
  {
    route_id: 'mapbox_route_1',
    display_name: 'Primary Route (via I-55 S, I-30 W)',
    rank: 1,
    distance_miles: 924.6,
    distance_km: 1488.0,
    duration_seconds: 50400,
    duration_formatted: '14h 0m',
    risk_assessment: {
      overall_risk_level: 'moderate',
      risk_score: 16.5,
      severe_risk_miles: 0.0,
      high_risk_miles: 0.0,
      moderate_risk_miles: 45.2,
      low_risk_miles: 879.4,
      no_travel_miles: 0.0,
      unknown_risk_miles: 0.0,
      no_travel_segments_count: 0,
      no_travel_warning: false,
      data_quality: 'available',
    },
    recommendation: {
      rank: 1,
      is_recommended: true,
      status: 'recommended',
      explanation:
        'Recommended as the safest available route. Completely avoids severe and high-risk weather hazards (0.0 severe miles, 0.0 high miles), maintaining the lowest average risk score (16.5) and the shortest travel time (14h 0m).',
      eligibility: 'eligible',
      assessment_status: 'complete',
    },
  },
  {
    route_id: 'mapbox_route_2',
    display_name: 'Alternative 1 (via I-57 S, I-40 W)',
    rank: 2,
    distance_miles: 952.1,
    distance_km: 1532.3,
    duration_seconds: 52200,
    duration_formatted: '14h 30m',
    risk_assessment: {
      overall_risk_level: 'high',
      risk_score: 24.8,
      severe_risk_miles: 0.0,
      high_risk_miles: 18.5,
      moderate_risk_miles: 62.0,
      low_risk_miles: 871.6,
      no_travel_miles: 0.0,
      unknown_risk_miles: 0.0,
      no_travel_segments_count: 0,
      no_travel_warning: false,
      data_quality: 'available',
    },
    recommendation: {
      rank: 2,
      is_recommended: false,
      status: 'viable_alternative',
      explanation:
        'Viable alternative route (Rank 2): 0.0 severe miles, 18.5 high-risk miles, average risk score 24.8, travel time 14h 30m (+18.5 mi high-risk weather, +30 min travel time vs Recommended Route).',
      eligibility: 'eligible',
      assessment_status: 'complete',
    },
  },
  {
    route_id: 'mapbox_route_3',
    display_name: 'Alternative 2 (via I-70 W, I-44 W)',
    rank: 3,
    distance_miles: 988.4,
    distance_km: 1590.7,
    duration_seconds: 54600,
    duration_formatted: '15h 10m',
    risk_assessment: {
      overall_risk_level: 'severe',
      risk_score: 48.2,
      severe_risk_miles: 35.0,
      high_risk_miles: 42.0,
      moderate_risk_miles: 80.0,
      low_risk_miles: 831.4,
      no_travel_miles: 0.0,
      unknown_risk_miles: 0.0,
      no_travel_segments_count: 0,
      no_travel_warning: false,
      data_quality: 'available',
    },
    recommendation: {
      rank: 3,
      is_recommended: false,
      status: 'not_recommended',
      explanation:
        'NOT RECOMMENDED (Rank 3): Encounters 35.0 miles of severe weather and 42.0 miles of high-risk conditions (+35.0 mi severe weather vs Recommended Route). High risk of weather-related transport disruption.',
      eligibility: 'eligible',
      assessment_status: 'complete',
    },
  },
]

export default function App() {
  const [isSubmitted, setIsSubmitted] = useState(false)
  const [queryParams, setQueryParams] = useState({
    origin: 'Chicago, IL',
    destination: 'Dallas, TX',
    loadWeightLb: 45000,
  })

  const handleFormSubmit = (formData) => {
    setQueryParams(formData)
    setIsSubmitted(true)
  }

  const handleReset = () => {
    setIsSubmitted(false)
  }

  return (
    <div className="app-container">
      <Header onReset={handleReset} />

      <main className="dashboard-layout">
        {/* Left Column: Form & Risk Reference */}
        <aside className="dashboard-sidebar" aria-label="Dispatch Input Controls">
          <RouteForm onSubmit={handleFormSubmit} isSubmitted={isSubmitted} />
          <RiskThresholdReference />
        </aside>

        {/* Right Column: Map Canvas Placeholder & Evaluated Route Cards */}
        <section className="dashboard-main" aria-label="Route Map and Evaluation Results">
          <MapPlaceholder
            plannedOrigin={queryParams.origin}
            plannedDestination={queryParams.destination}
            isPlanned={isSubmitted}
          />

          <RouteResults
            routes={DEMO_ROUTE_OPTIONS}
            isSubmitted={isSubmitted}
            queryParams={queryParams}
          />
        </section>
      </main>

      <footer className="app-footer">
        <div className="footer-content">
          <span>Weather-Aware Truck Routing &bull; Commercial Dispatch Platform</span>
          <span className="footer-meta">
            Backend Steps 1–7 Implemented &bull; Step 8 Frontend UI Mode &bull; Step 9 Live Map Integration Pending
          </span>
        </div>
      </footer>
    </div>
  )
}
