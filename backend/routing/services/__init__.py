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
from .recommendation_engine import BaseRecommendationEngine
from .recommendation import (
    RouteRecommendationService,
    STATUS_RECOMMENDED,
    STATUS_VIABLE_ALTERNATIVE,
    STATUS_NOT_RECOMMENDED,
    STATUS_PENDING,
    ELIGIBILITY_ELIGIBLE,
    ELIGIBILITY_NO_TRAVEL,
    ELIGIBILITY_INCOMPLETE,
    ASSESSMENT_COMPLETE,
    ASSESSMENT_PARTIAL,
    ASSESSMENT_UNAVAILABLE,
)

__all__ = [
    "BaseRouteEngine",
    "BaseWeatherEngine",
    "BaseRiskEngine",
    "BaseRecommendationEngine",
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
    "RouteRecommendationService",
    "STATUS_RECOMMENDED",
    "STATUS_VIABLE_ALTERNATIVE",
    "STATUS_NOT_RECOMMENDED",
    "STATUS_PENDING",
    "ELIGIBILITY_ELIGIBLE",
    "ELIGIBILITY_NO_TRAVEL",
    "ELIGIBILITY_INCOMPLETE",
    "ASSESSMENT_COMPLETE",
    "ASSESSMENT_PARTIAL",
    "ASSESSMENT_UNAVAILABLE",
]
