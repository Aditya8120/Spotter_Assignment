import React, { useState } from 'react'
import { Header } from './components/Header'
import { RouteForm } from './components/RouteForm'
import { InteractiveMap } from './components/InteractiveMap'
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
  const [selectedRouteId, setSelectedRouteId] = useState(null)
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
        setSelectedRouteId(null)
        setRecommendationSummary(null)
      } else if (response && response.status === 'planned') {
        const plannedRoutes = response.routes || []
        setRoutes(plannedRoutes)
        setRecommendationSummary(response.recommendation_summary || null)
        setIsPendingSetup(false)

        // Automatically select the recommended route or first route
        if (plannedRoutes.length > 0) {
          const recommended = plannedRoutes.find((r) => r.recommendation?.is_recommended)
          setSelectedRouteId(recommended ? recommended.route_id : plannedRoutes[0].route_id)
        } else {
          setSelectedRouteId(null)
        }
      } else {
        const fallbackRoutes = response?.routes || []
        setRoutes(fallbackRoutes)
        setRecommendationSummary(response?.recommendation_summary || null)
        setSelectedRouteId(fallbackRoutes[0]?.route_id || null)
      }
    } catch (err) {
      setError(err)
      setRoutes([])
      setSelectedRouteId(null)
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
    setSelectedRouteId(null)
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

        {/* Right Column: Interactive Route Map & Live Route Results */}
        <section className="dashboard-main" aria-label="Route Map and Evaluation Results">
          <InteractiveMap
            routes={routes}
            selectedRouteId={selectedRouteId}
            onSelectRoute={setSelectedRouteId}
            isLoading={isLoading}
            error={error}
            isPendingSetup={isPendingSetup}
            hasSearched={hasSearched}
            queryParams={queryParams}
          />

          <RouteResults
            routes={routes}
            selectedRouteId={selectedRouteId}
            onSelectRoute={setSelectedRouteId}
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
            Interactive Leaflet Vector Map &bull; Step 10 Complete &bull; OpenStreetMap Data &copy; OSM Contributors
          </span>
        </div>
      </footer>
    </div>
  )
}
