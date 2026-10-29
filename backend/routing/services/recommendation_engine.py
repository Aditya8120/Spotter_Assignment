"""
Modular Route Recommendation Engine interface.
Defines the abstract base contract for ranking route options and generating safety recommendations.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseRecommendationEngine(ABC):
    """Abstract base class for route recommendation and ranking engines."""

    @abstractmethod
    def rank_routes(
        self,
        routes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Ranks route options lexicographically by safety criteria, applies safety constraints,
        and attaches recommendation details and rank to each route.

        :param routes: List of route dictionaries with attached risk assessments.
        :return: Sorted list of route dictionaries, ordered from Rank 1 to Rank N.
        """
        raise NotImplementedError("Recommendation engine is not implemented.")

    @abstractmethod
    def build_recommendation_summary(
        self,
        ranked_routes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Builds a high-level summary of the recommendation outcome for the overall API response.

        :param ranked_routes: List of routes that have already been ranked.
        :return: Summary dictionary with top recommendation, safety flags, and executive rationale.
        """
        raise NotImplementedError("Recommendation summary generation is not implemented.")
