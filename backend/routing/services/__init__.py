"""
Services package for routing, weather retrieval, and risk scoring.
"""
from .route_engine import BaseRouteEngine
from .weather_engine import BaseWeatherEngine
from .risk_engine import BaseRiskEngine
from .mapbox import (
    MapboxRoutingService,
    MapboxServiceError,
    MapboxConfigurationError,
    MapboxAuthenticationError,
    MapboxRateLimitError,
    MapboxTimeoutError,
    MapboxConnectionError,
    MapboxNoRouteError,
    MapboxGeocodingError,
)
from .open_meteo import (
    OpenMeteoWeatherService,
    WeatherServiceError,
    WeatherProviderError,
    WeatherTimeoutError,
    WeatherConnectionError,
    WeatherRateLimitError,
)
from .risk_scoring import (
    WeatherRiskService,
    RiskScoringError,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MODERATE,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_SEVERE,
    RISK_LEVEL_NO_TRAVEL,
    RISK_LEVEL_UNKNOWN,
)

__all__ = [
    "BaseRouteEngine",
    "BaseWeatherEngine",
    "BaseRiskEngine",
    "MapboxRoutingService",
    "MapboxServiceError",
    "MapboxConfigurationError",
    "MapboxAuthenticationError",
    "MapboxRateLimitError",
    "MapboxTimeoutError",
    "MapboxConnectionError",
    "MapboxNoRouteError",
    "MapboxGeocodingError",
    "OpenMeteoWeatherService",
    "WeatherServiceError",
    "WeatherProviderError",
    "WeatherTimeoutError",
    "WeatherConnectionError",
    "WeatherRateLimitError",
    "WeatherRiskService",
    "RiskScoringError",
    "RISK_LEVEL_LOW",
    "RISK_LEVEL_MODERATE",
    "RISK_LEVEL_HIGH",
    "RISK_LEVEL_SEVERE",
    "RISK_LEVEL_NO_TRAVEL",
    "RISK_LEVEL_UNKNOWN",
]
