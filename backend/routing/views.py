import logging
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

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


