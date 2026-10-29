"""
Modular Risk Engine interface.
Future implementations will score weather hazard risks based on vehicle characteristics (e.g., load weight).
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseRiskEngine(ABC):
    """Abstract base class for weather risk assessment engines."""

    @abstractmethod
    def evaluate_route_risk(
        self,
        route_data: Dict[str, Any],
        load_weight_lb: float,
    ) -> Dict[str, Any]:
        """Assess overall risk and generate recommendation for a truck route."""
        raise NotImplementedError("Risk engine is not yet implemented.")
