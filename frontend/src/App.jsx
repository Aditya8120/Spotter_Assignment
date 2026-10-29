import React, { useState } from 'react'
import { Header } from './components/Header'
import { RouteForm } from './components/RouteForm'
import { MapPlaceholder } from './components/MapPlaceholder'
import { RouteResults } from './components/RouteResults'
import { RiskThresholdReference } from './components/RiskThresholdReference'
import { planRoutes } from './services/api'
import './App.css'

export default function App() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)
  const [isPendingSetup, setIsPendingSetup] = useState(false)
  const [pendingSetupMessage, setPendingSetupMessage] = useState('')
  const [routes, setRoutes] = useState([])
  const [recommendationSummary, setRecommendationSummary] = useState(null)
  const [hasSearched, setHasSearched] = useState(false)
  const [queryParams, setQueryParams] = useState({
    origin: 'Chicago, IL',
    destination: 'Dallas, TX',
    loadWeightLb: 45000,
    checkpointIntervalMiles: 25,
  })

  const handleFormSubmit = async (formData) => {
    setQueryParams(formData)
    setIsLoading(true)
    setError(null)
    setIsPendingSetup(false)
    setPendingSetupMessage('')
    setHasSearched(true)

    try {
      const response = await planRoutes(formData)

      if (response && response._isPendingSetup) {
        setIsPendingSetup(true)
        setPendingSetupMessage(response.message || '')
        setRoutes([])
        setRecommendationSummary(null)
      } else if (response && response.status === 'planned') {
        setRoutes(response.routes || [])
        setRecommendationSummary(response.recommendation_summary || null)
        setIsPendingSetup(false)
      } else {
        setRoutes(response?.routes || [])
        setRecommendationSummary(response?.recommendation_summary || null)
      }
    } catch (err) {
      setError(err)
      setRoutes([])
      setRecommendationSummary(null)
    } finally {
      setIsLoading(false)
    }
  }

  const handleReset = () => {
    setError(null)
    setIsPendingSetup(false)
    setPendingSetupMessage('')
    setRoutes([])
    setRecommendationSummary(null)
    setHasSearched(false)
  }

  return (
    <div className="app-container">
      <Header onReset={handleReset} />

      <main className="dashboard-layout">
        {/* Left Column: Form & Risk Reference */}
        <aside className="dashboard-sidebar" aria-label="Dispatch Input Controls">
          <RouteForm
            onSubmit={handleFormSubmit}
            isLoading={isLoading}
            serverFieldErrors={error?.fieldErrors || {}}
            initialValues={queryParams}
          />
          <RiskThresholdReference />
        </aside>

        {/* Right Column: Map Canvas Placeholder & Live Route Results */}
        <section className="dashboard-main" aria-label="Route Map and Evaluation Results">
          <MapPlaceholder
            plannedOrigin={queryParams.origin}
            plannedDestination={queryParams.destination}
            isPlanned={hasSearched}
          />

          <RouteResults
            routes={routes}
            recommendationSummary={recommendationSummary}
            isLoading={isLoading}
            error={error}
            isPendingSetup={isPendingSetup}
            pendingSetupMessage={pendingSetupMessage}
            hasSearched={hasSearched}
            queryParams={queryParams}
          />
        </section>
      </main>

      <footer className="app-footer">
        <div className="footer-content">
          <span>Weather-Aware Truck Routing &bull; Commercial Dispatch Platform</span>
          <span className="footer-meta">
            Backend API Connected &bull; Step 9 Integration Complete &bull; Interactive Mapbox Canvas (Step 10)
          </span>
        </div>
      </footer>
    </div>
  )
}
