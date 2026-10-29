import logging
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .serializers import (
    RoutePlanRequestSerializer,
    RoutePlanResponseSerializer,
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
    Returns a placeholder response with status 'not_implemented' until routing and weather services are integrated.
    POST /api/routes/
    """
    serializer = RoutePlanRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated = serializer.validated_data
    departure_dt = validated['departure_datetime']

    response_payload = {
        "status": "not_implemented",
        "message": (
            "Route planning request validated successfully. Routing engine, "
            "weather data integration, and hazard risk scoring are pending in future steps."
        ),
        "request_summary": {
            "origin": validated['origin'],
            "destination": validated['destination'],
            "departure_datetime": departure_dt,
            "load_weight_lb": validated['load_weight_lb'],
        },
        "routes": [],
    }

    response_serializer = RoutePlanResponseSerializer(instance=response_payload)
    return Response(response_serializer.data, status=status.HTTP_200_OK)




