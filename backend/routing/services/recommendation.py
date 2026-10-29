"""
Weather-Aware Route Recommendation and Ranking Service.

Implements lexicographic route ranking following the exact priority order:
1. Fewest miles classified as Severe.
2. Fewest miles classified as High.
3. Lowest average risk score.
4. Shortest travel time (duration).

Enforces critical safety constraints:
- Safety Tier Governance: Routes with No Travel segments are segregated and cannot be
  recommended when safe routes without No Travel segments are available.
- All-Unsafe Detection: When all available routes contain No Travel segments, the service
  explicitly flags that no route is safe and marks all routes as not recommended.
- Incomplete Weather Governance: Routes with missing or partial weather data are never silently
  treated as safer than fully assessed routes and cannot certify safety.
- Deterministic Tie-Breaking: When all four ranking criteria are tied, ordering is strictly
  deterministic using route identifiers and original sequence.
"""
from typing import Any, Dict, List, Optional, Tuple
import logging

from .recommendation_engine import BaseRecommendationEngine

logger = logging.getLogger(__name__)

# Recommendation Status Constants
STATUS_RECOMMENDED = "recommended"
STATUS_VIABLE_ALTERNATIVE = "viable_alternative"
STATUS_NOT_RECOMMENDED = "not_recommended"
STATUS_PENDING = "pending"

# Route Safety Eligibility Constants
ELIGIBILITY_ELIGIBLE = "eligible"
ELIGIBILITY_NO_TRAVEL = "no_travel_hazard"
ELIGIBILITY_INCOMPLETE = "incomplete_weather_data"

# Assessment Data Quality Constants
ASSESSMENT_COMPLETE = "complete"
ASSESSMENT_PARTIAL = "partial"
ASSESSMENT_UNAVAILABLE = "unavailable"

# Safety Tiers for Partitioning
TIER_ELIGIBLE = 0       # Fully assessed, 0 No Travel miles
TIER_INCOMPLETE = 1     # Incomplete weather data, 0 No Travel miles
TIER_NO_TRAVEL = 2      # Contains No Travel segments


class RouteRecommendationService(BaseRecommendationEngine):
    """
    Dedicated recommendation service ranking truck routes based on multi-hazard weather risk.
    """

    RANKING_PRIORITY = [
        "1. Fewest miles classified as Severe",
        "2. Fewest miles classified as High",
        "3. Lowest average risk score",
        "4. Shortest travel time",
    ]

    SAFETY_POLICY = (
        "Routes containing any No Travel segments are strictly ineligible for recommendation "
        "when safe alternatives exist. If every available route contains a No Travel segment, "
        "the engine flags that no route is considered safe and advises postponing departure."
    )

    DATA_QUALITY_POLICY = (
        "Routes with incomplete or unavailable weather forecasts are never silently treated as safer "
        "than fully assessed routes. Unassessed segments are flagged, and incomplete routes cannot be "
        "recommended if safe, fully assessed routes are available."
    )

    def rank_routes(
        self,
        routes: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Ranks route options lexicographically by safety criteria, applies safety constraints,
        and updates each route dictionary with rank, recommendation status, and human-readable explanation.

        :param routes: List of route dictionaries with attached risk assessments.
        :return: Sorted list of routes from Rank 1 to Rank N.
        """
        if not routes:
            return []

        # 1. Extract standardized metrics and determine safety tiers
        annotated: List[Dict[str, Any]] = []
        for idx, route in enumerate(routes):
            metrics = self._extract_metrics(route)
            assessment_status = self._determine_assessment_status(metrics)
            safety_tier, eligibility = self._determine_safety_tier(metrics, assessment_status)
            annotated.append({
                "route": route,
                "metrics": metrics,
                "assessment_status": assessment_status,
                "safety_tier": safety_tier,
                "eligibility": eligibility,
                "original_index": idx,
            })

        # 2. Check global route pool states
        all_no_travel = all(item["safety_tier"] == TIER_NO_TRAVEL for item in annotated)
        all_incomplete = all(item["safety_tier"] == TIER_INCOMPLETE for item in annotated)

        # 3. Sort lexicographically
        def sort_key(item: Dict[str, Any]) -> Tuple:
            m = item["metrics"]
            r_id = str(item["route"].get("route_id", ""))
            orig_idx = item["original_index"]
            avg_score = m["average_risk_score"]
            avg_score_key = float(avg_score) if avg_score is not None else float("inf")
            duration_key = m["duration_seconds"] if m["duration_seconds"] is not None else float("inf")

            if all_no_travel:
                # When all routes have No Travel, minimize extreme danger miles first,
                # then apply the 4 criteria: severe miles, high miles, avg score, duration
                return (
                    round(m["no_travel_miles"], 2),
                    round(m["severe_risk_miles"], 2),
                    round(m["high_risk_miles"], 2),
                    avg_score_key,
                    duration_key,
                    r_id,
                    orig_idx,
                )
            elif all_incomplete:
                # When all routes have incomplete weather, minimize unassessed miles first,
                # then apply detected severe, high, avg score, duration
                return (
                    round(m["unknown_risk_miles"], 2),
                    round(m["severe_risk_miles"], 2),
                    round(m["high_risk_miles"], 2),
                    avg_score_key,
                    duration_key,
                    r_id,
                    orig_idx,
                )
            else:
                # Standard safety tiering: Tier 0 (eligible) < Tier 1 (incomplete) < Tier 2 (No Travel)
                # Within Tier 0, order strictly follows the assignment's exact 4 criteria:
                # 1. Fewest severe miles
                # 2. Fewest high miles
                # 3. Lowest average risk score
                # 4. Shortest travel time
                return (
                    item["safety_tier"],
                    round(m["severe_risk_miles"], 2),
                    round(m["high_risk_miles"], 2),
                    avg_score_key,
                    duration_key,
                    r_id,
                    orig_idx,
                )

        annotated.sort(key=sort_key)

        # 4. Assign ranks, recommendation statuses, and human-readable explanations
        ranked_routes: List[Dict[str, Any]] = []
        top_item = annotated[0] if annotated else None

        for rank_idx, item in enumerate(annotated, start=1):
            route = item["route"]
            metrics = item["metrics"]
            tier = item["safety_tier"]
            eligibility = item["eligibility"]
            assessment_status = item["assessment_status"]

            # Determine recommendation status & is_recommended
            if all_no_travel:
                is_rec = False
                status = STATUS_NOT_RECOMMENDED
            elif rank_idx == 1:
                if tier == TIER_ELIGIBLE:
                    is_rec = True
                    status = STATUS_RECOMMENDED
                elif all_incomplete:
                    # When all routes lack complete weather, recommend fastest with explicit data warning
                    is_rec = True
                    status = STATUS_RECOMMENDED
                else:
                    is_rec = False
                    status = STATUS_NOT_RECOMMENDED
            else:
                if tier == TIER_ELIGIBLE or all_incomplete:
                    is_rec = False
                    status = STATUS_VIABLE_ALTERNATIVE
                else:
                    is_rec = False
                    status = STATUS_NOT_RECOMMENDED

            # Build human-readable explanation
            explanation = self._generate_explanation(
                rank=rank_idx,
                item=item,
                top_item=top_item,
                total_routes=len(annotated),
                all_no_travel=all_no_travel,
                all_incomplete=all_incomplete,
            )

            # Build standardized recommendation dictionary
            recommendation_payload = {
                "rank": rank_idx,
                "is_recommended": is_rec,
                "status": status,
                "explanation": explanation,
                "eligibility": eligibility,
                "assessment_status": assessment_status,
                "ranking_metrics": {
                    "severe_risk_miles": metrics["severe_risk_miles"],
                    "high_risk_miles": metrics["high_risk_miles"],
                    "average_risk_score": metrics["average_risk_score"],
                    "duration_seconds": metrics["duration_seconds"],
                    "duration_formatted": metrics["duration_formatted"],
                    "no_travel_miles": metrics["no_travel_miles"],
                    "no_travel_segments_count": metrics["no_travel_segments_count"],
                    "unknown_risk_miles": metrics["unknown_risk_miles"],
                },
            }

            route["rank"] = rank_idx
            route["recommendation"] = recommendation_payload
            ranked_routes.append(route)

        return ranked_routes

    def build_recommendation_summary(
        self,
        ranked_routes: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Builds a comprehensive, human-readable summary of the recommendation outcome
        for the top-level API response.
        """
        if not ranked_routes:
            return {
                "recommended_route_id": None,
                "all_routes_unsafe": False,
                "incomplete_data_warning": False,
                "total_options_evaluated": 0,
                "ranking_priority": self.RANKING_PRIORITY,
                "safety_policy": self.SAFETY_POLICY,
                "data_quality_policy": self.DATA_QUALITY_POLICY,
                "executive_summary": "No route options were provided to evaluate.",
            }

        top_route = ranked_routes[0]
        top_rec = top_route.get("recommendation", {})
        top_is_rec = top_rec.get("is_recommended", False)
        all_no_travel = all(
            r.get("recommendation", {}).get("eligibility") == ELIGIBILITY_NO_TRAVEL
            for r in ranked_routes
        )
        all_incomplete = all(
            r.get("recommendation", {}).get("assessment_status") in (ASSESSMENT_PARTIAL, ASSESSMENT_UNAVAILABLE)
            for r in ranked_routes
        )

        recommended_id = top_route.get("route_id") if top_is_rec else None

        if all_no_travel:
            executive_summary = (
                f"NO SAFE ROUTE AVAILABLE: All {len(ranked_routes)} route options encounter extreme weather "
                "with No Travel advisories (winds >= 55 mph or severe blizzard conditions). Driving is "
                "unsafe and prohibited under carrier safety standards. Delaying departure is strongly advised."
            )
        elif all_incomplete:
            executive_summary = (
                f"WEATHER DATA INCOMPLETE: Weather forecast data was unavailable or partial for all "
                f"{len(ranked_routes)} route options. Route safety cannot be certified."
            )
        elif top_is_rec:
            executive_summary = (
                f"Route '{top_route.get('display_name', top_route.get('route_id'))}' is recommended as the safest route. "
                f"{top_rec.get('explanation', '')}"
            )
        else:
            executive_summary = (
                f"Top-ranked route '{top_route.get('display_name')}' cannot be recommended due to safety "
                f"or data quality constraints: {top_rec.get('explanation', '')}"
            )

        return {
            "recommended_route_id": recommended_id,
            "all_routes_unsafe": all_no_travel,
            "incomplete_data_warning": all_incomplete,
            "total_options_evaluated": len(ranked_routes),
            "ranking_priority": self.RANKING_PRIORITY,
            "safety_policy": self.SAFETY_POLICY,
            "data_quality_policy": self.DATA_QUALITY_POLICY,
            "executive_summary": executive_summary,
        }

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _extract_metrics(self, route: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts and normalizes relevant ranking metrics from a route dictionary."""
        risk = route.get("risk_assessment") or {}
        duration_sec = route.get("duration_seconds")
        if duration_sec is not None:
            try:
                duration_sec = int(duration_sec)
            except (ValueError, TypeError):
                duration_sec = None

        return {
            "severe_risk_miles": round(float(risk.get("severe_risk_miles") or 0.0), 2),
            "high_risk_miles": round(float(risk.get("high_risk_miles") or 0.0), 2),
            "average_risk_score": risk.get("risk_score"),
            "duration_seconds": duration_sec,
            "duration_formatted": route.get("duration_formatted", ""),
            "no_travel_miles": round(float(risk.get("no_travel_miles") or 0.0), 2),
            "no_travel_segments_count": int(risk.get("no_travel_segments_count") or 0),
            "no_travel_warning": bool(risk.get("no_travel_warning", False)),
            "unknown_risk_miles": round(float(risk.get("unknown_risk_miles") or 0.0), 2),
            "total_distance_miles": round(float(route.get("distance_miles") or risk.get("total_distance_miles") or 0.0), 2),
            "data_quality": risk.get("data_quality", "available"),
            "display_name": route.get("display_name", route.get("route_id", "Route")),
        }

    def _determine_assessment_status(self, metrics: Dict[str, Any]) -> str:
        """Determines whether weather risk assessment is complete, partial, or unavailable."""
        dq = metrics.get("data_quality", "available")
        unk_miles = metrics["unknown_risk_miles"]
        total_miles = metrics["total_distance_miles"]

        if dq == "unavailable" or (total_miles > 0 and unk_miles >= total_miles):
            return ASSESSMENT_UNAVAILABLE
        if dq == "partial" or unk_miles > 0:
            return ASSESSMENT_PARTIAL
        return ASSESSMENT_COMPLETE

    def _determine_safety_tier(
        self,
        metrics: Dict[str, Any],
        assessment_status: str,
    ) -> Tuple[int, str]:
        """
        Assigns route to safety tier and eligibility status:
        - Tier 0: Complete assessment, zero No Travel miles (Eligible)
        - Tier 1: Incomplete assessment, zero No Travel miles (Conditional / Incomplete)
        - Tier 2: Contains No Travel segments (Ineligible)
        """
        if metrics["no_travel_miles"] > 0 or metrics["no_travel_segments_count"] > 0 or metrics["no_travel_warning"]:
            return TIER_NO_TRAVEL, ELIGIBILITY_NO_TRAVEL

        if assessment_status in (ASSESSMENT_PARTIAL, ASSESSMENT_UNAVAILABLE):
            return TIER_INCOMPLETE, ELIGIBILITY_INCOMPLETE

        return TIER_ELIGIBLE, ELIGIBILITY_ELIGIBLE

    def _generate_explanation(
        self,
        rank: int,
        item: Dict[str, Any],
        top_item: Optional[Dict[str, Any]],
        total_routes: int,
        all_no_travel: bool,
        all_incomplete: bool,
    ) -> str:
        """Constructs a detailed, human-readable rationale for the route's rank and recommendation status."""
        m = item["metrics"]
        tier = item["safety_tier"]
        name = m["display_name"]
        sev = m["severe_risk_miles"]
        hi = m["high_risk_miles"]
        avg = m["average_risk_score"]
        avg_str = f"{avg:.1f}" if avg is not None else "N/A"
        dur_str = m["duration_formatted"] or (f"{m['duration_seconds'] // 60} min" if m["duration_seconds"] else "N/A")

        # 1. All routes have No Travel
        if all_no_travel:
            return (
                f"NOT RECOMMENDED (Rank {rank}): Route encounters {m['no_travel_miles']:.1f} miles of extreme "
                f"No Travel conditions across {m['no_travel_segments_count']} segment(s). All evaluated routes "
                "violate safety standards; commercial driving is unsafe and not advised."
            )

        # 2. All routes have incomplete weather data
        if all_incomplete:
            if rank == 1:
                return (
                    f"Recommended route (Rank 1): Shortest travel time ({dur_str}). "
                    f"CAUTION: Weather forecast data was unavailable or incomplete ({m['unknown_risk_miles']:.1f} mi unassessed); "
                    "weather hazards could not be certified."
                )
            return (
                f"Viable alternative route (Rank {rank}): Travel time {dur_str}. "
                f"CAUTION: Weather forecast data was unavailable or incomplete ({m['unknown_risk_miles']:.1f} mi unassessed)."
            )

        # 3. Route has No Travel while safe routes exist
        if tier == TIER_NO_TRAVEL:
            return (
                f"NOT RECOMMENDED (Rank {rank}): Route violates critical safety policy with {m['no_travel_miles']:.1f} "
                f"miles of No Travel conditions across {m['no_travel_segments_count']} segment(s). Safe alternative "
                "routes without No Travel conditions are available."
            )

        # 4. Route has incomplete weather data while complete routes exist
        if tier == TIER_INCOMPLETE:
            return (
                f"NOT RECOMMENDED (Rank {rank}): Route has incomplete weather data ({m['unknown_risk_miles']:.1f} mi "
                "unassessed). Routes with incomplete forecasts cannot be certified as safe over fully assessed alternatives."
            )

        # 5. Rank 1 (Recommended Route)
        if rank == 1:
            if total_routes == 1:
                return (
                    f"Recommended as the safest available route. Assessed with {sev:.1f} severe miles, "
                    f"{hi:.1f} high-risk miles, average risk score of {avg_str}, and travel time of {dur_str}."
                )

            # Compare against runner-up (Rank 2) if available
            alt_m = None
            if total_routes > 1 and top_item is not None:
                # We can highlight why Rank 1 won over alternative
                pass

            reasons: List[str] = []
            if sev == 0.0 and hi == 0.0:
                reasons.append("avoids all severe and high-risk weather hazards")
            elif sev == 0.0:
                reasons.append(f"avoids all severe weather hazards with only {hi:.1f} high-risk miles")
            else:
                reasons.append(f"minimizes severe weather exposure to {sev:.1f} miles")

            reasons.append(f"average risk score: {avg_str}")
            reasons.append(f"travel time: {dur_str}")

            return f"Recommended as safest route: {', '.join(reasons)}."

        # 6. Viable Alternative (Rank > 1, Tier 0)
        diff_notes: List[str] = []
        if top_item:
            top_m = top_item["metrics"]
            top_sev = top_m["severe_risk_miles"]
            top_hi = top_m["high_risk_miles"]
            top_avg = top_m["average_risk_score"]
            top_dur = top_m["duration_seconds"]

            if sev > top_sev:
                diff_notes.append(f"+{sev - top_sev:.1f} mi severe weather")
            elif hi > top_hi:
                diff_notes.append(f"+{hi - top_hi:.1f} mi high-risk weather")
            elif avg is not None and top_avg is not None and avg > top_avg:
                diff_notes.append(f"+{avg - top_avg:.1f} higher average risk score")
            elif m["duration_seconds"] is not None and top_dur is not None and m["duration_seconds"] > top_dur:
                diff_sec = m["duration_seconds"] - top_dur
                diff_notes.append(f"+{diff_sec // 60} min travel time")

        comparison = f" ({', '.join(diff_notes)} vs Recommended Route)" if diff_notes else ""
        return (
            f"Viable alternative route (Rank {rank}): {sev:.1f} severe miles, {hi:.1f} high-risk miles, "
            f"average risk score {avg_str}, travel time {dur_str}{comparison}."
        )
