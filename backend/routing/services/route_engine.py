"""
Modular Route Engine interface.
Future implementations will connect to routing providers (e.g., OSRM, ORS, Google Maps).
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseRouteEngine(ABC):
    """Abstract base class for route generation providers."""

    @abstractmethod
    def calculate_routes(
        self,
        origin: Dict[str, Any],
        destination: Dict[str, Any],
        departure_datetime: str,
        load_weight_lb: float,
    ) -> List[Dict[str, Any]]:
        """Calculate up to three candidate routes between origin and destination."""
        raise NotImplementedError("Route calculation engine is not yet implemented.")
