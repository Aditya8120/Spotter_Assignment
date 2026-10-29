import logging
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import (
    RoutePlanRequestSerializer,
    RoutePlanResponseSerializer,
)
from .services import (
    MapboxRoutingService,
    MapboxServiceError,
    MapboxConfigurationError,
    MapboxAuthenticationError,
    MapboxRateLimitError,
    MapboxTimeoutError,
    MapboxConnectionError,
    MapboxNoRouteError,
    MapboxGeocodingError,
    OpenMeteoWeatherService,
    WeatherRiskService,
    RouteRecommendationService,
)

logger = logging.getLogger(__name__)


@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint returning system status.
    GET /api/health/ -> {"status": "ok"}
    """
    try:
        return Response({"status": "ok"}, status=status.HTTP_200_OK)
    except Exception as exc:
        logger.error("Health check endpoint encountered an error: %s", exc, exc_info=True)
        return Response(
            {"status": "error", "message": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(['POST'])
def plan_routes(request):
    """
    Route planning endpoint.
    Validates input parameters (origin, destination, departure_datetime, load_weight_lb).
    Retrieves real route options from Mapbox Directions API.
    POST /api/routes/
    """
    serializer = RoutePlanRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated = serializer.validated_data
    departure_dt = validated['departure_datetime']
    checkpoint_interval = validated.get('checkpoint_interval_miles', 25)

    try:
        routing_service = MapboxRoutingService()
        routes = routing_service.calculate_routes(
            origin=validated['origin'],
            destination=validated['destination'],
            departure_datetime=departure_dt,
            load_weight_lb=validated['load_weight_lb'],
            checkpoint_interval_miles=checkpoint_interval,
        )
        # Fetch and attach weather forecasts for checkpoint arrival times
        weather_service = OpenMeteoWeatherService()
        weather_service.attach_weather_to_routes(routes)

        # Evaluate and attach weather hazard risk assessments based on load weight
        risk_service = WeatherRiskService()
        risk_service.attach_risk_to_routes(routes, load_weight_lb=validated['load_weight_lb'])

        # Lexicographically rank routes and attach safety recommendations
        recommendation_service = RouteRecommendationService()
        routes = recommendation_service.rank_routes(routes)
        recommendation_summary = recommendation_service.build_recommendation_summary(routes)
    except MapboxConfigurationError as exc:
        logger.warning("Mapbox routing unconfigured: %s", exc)
        return Response(
            {
                "status": "error",
                "code": "provider_not_configured",
                "message": "Routing provider is not configured. Missing MAPBOX_ACCESS_TOKEN in server environment.",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except MapboxAuthenticationError as exc:
        logger.error("Mapbox authentication error: %s", exc)
        return Response(
            {
                "status": "error",
                "code": "provider_auth_error",
                "message": "Routing provider authentication failed. Please verify provider credentials.",
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except MapboxRateLimitError as exc:
        logger.warning("Mapbox rate limit reached: %s", exc)
        return Response(
            {
                "status": "error",
                "code": "rate_limit_exceeded",
                "message": "Routing provider rate limit reached. Please retry after a brief delay.",
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    except MapboxTimeoutError as exc:
        logger.warning("Mapbox request timed out: %s", exc)
        return Response(
            {
                "status": "error",
                "code": "provider_timeout",
                "message": "Routing provider request timed out. Please try again.",
            },
            status=status.HTTP_504_GATEWAY_TIMEOUT,
        )
    except MapboxConnectionError as exc:
        logger.error("Mapbox network connection failure: %s", exc)
        return Response(
            {
                "status": "error",
                "code": "provider_connection_error",
                "message": "Unable to connect to routing provider network.",
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except MapboxNoRouteError as exc:
        logger.info("No route found between locations: %s", exc)
        return Response(
            {
                "status": "error",
                "code": "no_route_found",
                "message": "No driving route could be found between the specified origin and destination.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )
    except MapboxGeocodingError as exc:
        logger.info("Geocoding failure: %s", exc)
        return Response(
            {
                "status": "error",
                "code": "geocoding_failed",
                "message": str(exc),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    except MapboxServiceError as exc:
        logger.error("Mapbox service error: %s", exc)
        return Response(
            {
                "status": "error",
                "code": "provider_error",
                "message": "Routing provider encountered an error generating routes.",
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as exc:
        logger.error("Unexpected error in plan_routes: %s", exc, exc_info=True)
        return Response(
            {
                "status": "error",
                "code": "internal_error",
                "message": "An unexpected error occurred while calculating routes.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    response_payload = {
        "status": "planned",
        "message": (
            "Routes successfully calculated via Mapbox Directions API with weather forecasts from Open-Meteo, "
            "load-specific weather hazard risk assessments, and lexicographic safety recommendations. "
            "Note: Routes reflect standard driving directions and do not yet account for truck height/weight "
            "limits or road closures."
        ),
        "request_summary": {
            "origin": validated['origin'],
            "destination": validated['destination'],
            "departure_datetime": departure_dt,
            "load_weight_lb": validated['load_weight_lb'],
            "checkpoint_interval_miles": checkpoint_interval,
        },
        "routes": routes,
        "recommendation_summary": recommendation_summary,
    }

    response_serializer = RoutePlanResponseSerializer(instance=response_payload)
    return Response(response_serializer.data, status=status.HTTP_200_OK)





