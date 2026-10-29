"""
Modular Weather Engine interface.
Future implementations will connect to weather providers (e.g., Open-Meteo, NWS).
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseWeatherEngine(ABC):
    """Abstract base class for weather observation and forecast providers."""

    @abstractmethod
    def get_weather_for_checkpoints(
        self,
        checkpoints: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Retrieve weather observations/forecasts for given route checkpoints."""
        raise NotImplementedError("Weather engine is not yet implemented.")
