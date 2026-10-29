"""
Weather Risk Scoring Service for commercial truck routing.
Evaluates weather conditions against exact assignment thresholds for wind, precipitation, and snowfall,
applies truck load-weight elevation rules, handles missing weather data safely,
and calculates distance-weighted route risk summaries.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from .risk_engine import BaseRiskEngine

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Risk Level Constants and Numeric Score Mapping
# -------------------------------------------------------------------------

RISK_LEVEL_LOW = "low"
RISK_LEVEL_MODERATE = "moderate"
RISK_LEVEL_HIGH = "high"
RISK_LEVEL_SEVERE = "severe"
RISK_LEVEL_NO_TRAVEL = "no_travel"
RISK_LEVEL_UNKNOWN = "unknown"

VALID_RISK_LEVELS = [
    RISK_LEVEL_LOW,
    RISK_LEVEL_MODERATE,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_SEVERE,
    RISK_LEVEL_NO_TRAVEL,
    RISK_LEVEL_UNKNOWN,
]

# Severity ranking: higher rank indicates greater danger
SEVERITY_RANK: Dict[str, int] = {
    RISK_LEVEL_UNKNOWN: -1,
    RISK_LEVEL_LOW: 0,
    RISK_LEVEL_MODERATE: 1,
    RISK_LEVEL_HIGH: 2,
    RISK_LEVEL_SEVERE: 3,
    RISK_LEVEL_NO_TRAVEL: 4,
}

# Standard numeric risk score mapping (0 to 100 scale; None for unknown)
# Low: 0 - 20 (standard 10.0)
# Moderate: 21 - 45 (standard 35.0)
# High: 46 - 70 (standard 60.0)
# Severe: 71 - 90 (standard 80.0)
# No Travel: 91 - 100 (standard 100.0)
LEVEL_SCORES: Dict[str, Optional[float]] = {
    RISK_LEVEL_LOW: 10.0,
    RISK_LEVEL_MODERATE: 35.0,
    RISK_LEVEL_HIGH: 60.0,
    RISK_LEVEL_SEVERE: 80.0,
    RISK_LEVEL_NO_TRAVEL: 100.0,
    RISK_LEVEL_UNKNOWN: None,
}


# -------------------------------------------------------------------------
# Exceptions
# -------------------------------------------------------------------------

class RiskScoringError(Exception):
    """Base exception for risk scoring calculation errors."""
    pass


# -------------------------------------------------------------------------
# Service Implementation
# -------------------------------------------------------------------------

class WeatherRiskService(BaseRiskEngine):
    """
    Dedicated weather hazard risk scoring service for truck operations.
    Evaluates wind speed, precipitation intensity, and snowfall intensity against defined thresholds
    and vehicle load weight.
    """

    DOCUMENTED_ASSUMPTIONS: List[str] = [
        "Threshold evaluation: Wind speed (mph), precipitation intensity (in/h), and snowfall intensity (in/h) "
        "are evaluated independently; the most severe hazard governs the checkpoint risk level.",
        "Load-specific rules: Wind >= 55 mph enforces No Travel for all loads. Wind 45 to <55 mph enforces "
        "No Travel when load weight is > 30,000 lb. Wind 35 to <45 mph elevates to Severe when load weight is > 40,000 lb.",
        "Missing weather data: Checkpoints with missing weather measurements are explicitly marked with data quality "
        "'partial' or 'unavailable'. Missing data is never treated as zero and is never assigned Low risk.",
        "Segment attribution: Each checkpoint represents the route segment centered on its location "
        "(half-distance to previous checkpoint plus half-distance to next checkpoint; endpoints cover half-distance "
        "to adjacent checkpoint). Segment miles sum precisely to total route distance.",
        "Numeric scoring: Categorical risks map to standard scores (Low: 10, Moderate: 35, High: 60, Severe: 80, "
        "No Travel: 100, Unknown: None). Route score is the distance-weighted average over scored segments.",
    ]

    def evaluate_wind_risk(
        self,
        wind_speed_mph: Optional[float],
        load_weight_lb: float,
    ) -> Dict[str, Any]:
        """
        Evaluates wind risk incorporating assignment thresholds and load-specific rules:
        - Low: below 25 mph
        - Moderate: 25–34 mph
        - High: 35–44 mph (elevated to Severe if load > 40,000 lb)
        - Severe: 45–54 mph (elevated to No Travel if load > 30,000 lb)
        - No Travel: 55 mph or above (for every load)
        """
        if wind_speed_mph is None:
            return {
                "hazard": "wind",
                "risk_level": RISK_LEVEL_UNKNOWN,
                "score": None,
                "value": None,
                "unit": "mph",
                "reason": "Wind speed data is unavailable.",
                "is_elevated_by_load": False,
            }

        wind = float(wind_speed_mph)
        load = float(load_weight_lb)

        # Rule 1: Wind at or above 55 mph means No Travel for every load
        if wind >= 55.0:
            return {
                "hazard": "wind",
                "risk_level": RISK_LEVEL_NO_TRAVEL,
                "score": LEVEL_SCORES[RISK_LEVEL_NO_TRAVEL],
                "value": round(wind, 1),
                "unit": "mph",
                "reason": f"Extreme wind speed ({wind:.1f} mph >= 55 mph): No Travel advised for all vehicle weights.",
                "is_elevated_by_load": False,
            }

        # Rule 2: Wind from 45 to below 55 mph
        # Means No Travel when load weight is above 30,000 lb, else Severe
        if 45.0 <= wind < 55.0:
            if load > 30000.0:
                return {
                    "hazard": "wind",
                    "risk_level": RISK_LEVEL_NO_TRAVEL,
                    "score": LEVEL_SCORES[RISK_LEVEL_NO_TRAVEL],
                    "value": round(wind, 1),
                    "unit": "mph",
                    "reason": (
                        f"Wind speed ({wind:.1f} mph in 45-54 mph range) elevated to No Travel for heavy load "
                        f"({load:,.0f} lb > 30,000 lb)."
                    ),
                    "is_elevated_by_load": True,
                }
            return {
                "hazard": "wind",
                "risk_level": RISK_LEVEL_SEVERE,
                "score": LEVEL_SCORES[RISK_LEVEL_SEVERE],
                "value": round(wind, 1),
                "unit": "mph",
                "reason": f"Severe wind speed ({wind:.1f} mph in 45-54 mph range).",
                "is_elevated_by_load": False,
            }

        # Rule 3: Wind from 35 to below 45 mph
        # Means Severe when load weight is above 40,000 lb, else High
        if 35.0 <= wind < 45.0:
            if load > 40000.0:
                return {
                    "hazard": "wind",
                    "risk_level": RISK_LEVEL_SEVERE,
                    "score": LEVEL_SCORES[RISK_LEVEL_SEVERE],
                    "value": round(wind, 1),
                    "unit": "mph",
                    "reason": (
                        f"Wind speed ({wind:.1f} mph in 35-44 mph range) elevated to Severe for very heavy load "
                        f"({load:,.0f} lb > 40,000 lb)."
                    ),
                    "is_elevated_by_load": True,
                }
            return {
                "hazard": "wind",
                "risk_level": RISK_LEVEL_HIGH,
                "score": LEVEL_SCORES[RISK_LEVEL_HIGH],
                "value": round(wind, 1),
                "unit": "mph",
                "reason": f"High wind speed ({wind:.1f} mph in 35-44 mph range).",
                "is_elevated_by_load": False,
            }

        # Moderate: 25–34 mph
        if 25.0 <= wind < 35.0:
            return {
                "hazard": "wind",
                "risk_level": RISK_LEVEL_MODERATE,
                "score": LEVEL_SCORES[RISK_LEVEL_MODERATE],
                "value": round(wind, 1),
                "unit": "mph",
                "reason": f"Moderate wind speed ({wind:.1f} mph in 25-34 mph range).",
                "is_elevated_by_load": False,
            }

        # Low: below 25 mph
        return {
            "hazard": "wind",
            "risk_level": RISK_LEVEL_LOW,
            "score": LEVEL_SCORES[RISK_LEVEL_LOW],
            "value": round(wind, 1),
            "unit": "mph",
            "reason": f"Low wind speed ({wind:.1f} mph < 25 mph).",
            "is_elevated_by_load": False,
        }

    def evaluate_precipitation_risk(
        self,
        precip_rate_in_per_hour: Optional[float],
    ) -> Dict[str, Any]:
        """
        Evaluates liquid precipitation risk against assignment thresholds:
        - Low: below 0.10 in/h
        - Moderate: 0.10–0.25 in/h
        - High: above 0.25–0.50 in/h
        - Severe: above 0.50–1.00 in/h
        - No Travel: above 1.00 in/h
        """
        if precip_rate_in_per_hour is None:
            return {
                "hazard": "precipitation",
                "risk_level": RISK_LEVEL_UNKNOWN,
                "score": None,
                "value": None,
                "unit": "in/h",
                "reason": "Precipitation rate data is unavailable.",
            }

        rate = float(precip_rate_in_per_hour)

        if rate > 1.00:
            return {
                "hazard": "precipitation",
                "risk_level": RISK_LEVEL_NO_TRAVEL,
                "score": LEVEL_SCORES[RISK_LEVEL_NO_TRAVEL],
                "value": round(rate, 2),
                "unit": "in/h",
                "reason": f"Extreme precipitation ({rate:.2f} in/h > 1.00 in/h): Hydroplaning hazard, No Travel advised.",
            }
        if rate > 0.50:
            return {
                "hazard": "precipitation",
                "risk_level": RISK_LEVEL_SEVERE,
                "score": LEVEL_SCORES[RISK_LEVEL_SEVERE],
                "value": round(rate, 2),
                "unit": "in/h",
                "reason": f"Severe precipitation rate ({rate:.2f} in/h > 0.50 in/h).",
            }
        if rate > 0.25:
            return {
                "hazard": "precipitation",
                "risk_level": RISK_LEVEL_HIGH,
                "score": LEVEL_SCORES[RISK_LEVEL_HIGH],
                "value": round(rate, 2),
                "unit": "in/h",
                "reason": f"High precipitation rate ({rate:.2f} in/h > 0.25 in/h).",
            }
        if rate >= 0.10:
            return {
                "hazard": "precipitation",
                "risk_level": RISK_LEVEL_MODERATE,
                "score": LEVEL_SCORES[RISK_LEVEL_MODERATE],
                "value": round(rate, 2),
                "unit": "in/h",
                "reason": f"Moderate precipitation rate ({rate:.2f} in/h in 0.10-0.25 in/h range).",
            }
        return {
            "hazard": "precipitation",
            "risk_level": RISK_LEVEL_LOW,
            "score": LEVEL_SCORES[RISK_LEVEL_LOW],
            "value": round(rate, 2),
            "unit": "in/h",
            "reason": f"Low precipitation rate ({rate:.2f} in/h < 0.10 in/h).",
        }

    def evaluate_snowfall_risk(
        self,
        snowfall_rate_in_per_hour: Optional[float],
    ) -> Dict[str, Any]:
        """
        Evaluates snowfall risk against assignment thresholds:
        - Low: below 0.5 in/h
        - Moderate: 0.5–1.0 in/h
        - High: above 1.0–2.0 in/h
        - Severe: above 2.0–3.0 in/h
        - No Travel: above 3.0 in/h
        """
        if snowfall_rate_in_per_hour is None:
            return {
                "hazard": "snowfall",
                "risk_level": RISK_LEVEL_UNKNOWN,
                "score": None,
                "value": None,
                "unit": "in/h",
                "reason": "Snowfall rate data is unavailable.",
            }

        rate = float(snowfall_rate_in_per_hour)

        if rate > 3.00:
            return {
                "hazard": "snowfall",
                "risk_level": RISK_LEVEL_NO_TRAVEL,
                "score": LEVEL_SCORES[RISK_LEVEL_NO_TRAVEL],
                "value": round(rate, 2),
                "unit": "in/h",
                "reason": f"Extreme snowfall rate ({rate:.2f} in/h > 3.00 in/h): Whiteout / impassable road conditions.",
            }
        if rate > 2.00:
            return {
                "hazard": "snowfall",
                "risk_level": RISK_LEVEL_SEVERE,
                "score": LEVEL_SCORES[RISK_LEVEL_SEVERE],
                "value": round(rate, 2),
                "unit": "in/h",
                "reason": f"Severe snowfall rate ({rate:.2f} in/h > 2.00 in/h).",
            }
        if rate > 1.00:
            return {
                "hazard": "snowfall",
                "risk_level": RISK_LEVEL_HIGH,
                "score": LEVEL_SCORES[RISK_LEVEL_HIGH],
                "value": round(rate, 2),
                "unit": "in/h",
                "reason": f"High snowfall rate ({rate:.2f} in/h > 1.00 in/h).",
            }
        if rate >= 0.50:
            return {
                "hazard": "snowfall",
                "risk_level": RISK_LEVEL_MODERATE,
                "score": LEVEL_SCORES[RISK_LEVEL_MODERATE],
                "value": round(rate, 2),
                "unit": "in/h",
                "reason": f"Moderate snowfall rate ({rate:.2f} in/h in 0.50-1.00 in/h range).",
            }
        return {
            "hazard": "snowfall",
            "risk_level": RISK_LEVEL_LOW,
            "score": LEVEL_SCORES[RISK_LEVEL_LOW],
            "value": round(rate, 2),
            "unit": "in/h",
            "reason": f"Low snowfall rate ({rate:.2f} in/h < 0.50 in/h).",
        }

    def evaluate_checkpoint_risk(
        self,
        checkpoint: Dict[str, Any],
        load_weight_lb: float,
    ) -> Dict[str, Any]:
        """
        Evaluates weather conditions at a single checkpoint:
        - Computes individual wind, precipitation, and snowfall risk components.
        - Governs overall risk by the most severe applicable hazard.
        - Preserves missing weather data explicitly without defaulting to zero or assigning Low risk.
        """
        weather = checkpoint.get("weather") or {}
        weather_avail = weather.get("data_availability", "unavailable") if weather else "unavailable"

        # If weather is completely unrecorded or marked unavailable/out_of_horizon
        if not weather or weather_avail in ("unavailable", "out_of_forecast_horizon"):
            data_quality = weather_avail
            return {
                "risk_level": RISK_LEVEL_UNKNOWN,
                "risk_score": None,
                "risk_factors": ["Weather forecast data is unavailable for this checkpoint."],
                "risk_components": {
                    "wind": self.evaluate_wind_risk(None, load_weight_lb),
                    "precipitation": self.evaluate_precipitation_risk(None),
                    "snowfall": self.evaluate_snowfall_risk(None),
                },
                "risk_summary": "Weather data unavailable; risk cannot be determined.",
                "data_quality": data_quality,
            }

        wind_speed = weather.get("wind_speed_mph")
        precip_rate = weather.get("precipitation_in_per_hour")
        if precip_rate is None:
            precip_rate = weather.get("precipitation_rate_in_per_hour")
        snow_rate = weather.get("snowfall_in_per_hour")
        if snow_rate is None:
            snow_rate = weather.get("snowfall_rate_in_per_hour")

        wind_comp = self.evaluate_wind_risk(wind_speed, load_weight_lb)
        precip_comp = self.evaluate_precipitation_risk(precip_rate)
        snow_comp = self.evaluate_snowfall_risk(snow_rate)

        components = {
            "wind": wind_comp,
            "precipitation": precip_comp,
            "snowfall": snow_comp,
        }

        # Check data quality: count missing measurements
        missing_count = sum(1 for c in components.values() if c["risk_level"] == RISK_LEVEL_UNKNOWN)
        if missing_count == 0:
            data_quality = "available"
        elif missing_count == len(components):
            data_quality = "unavailable"
        else:
            data_quality = "partial"

        # Determine highest severity among known components
        known_components = [c for c in components.values() if c["risk_level"] != RISK_LEVEL_UNKNOWN]

        # Requirement 8: If all data is unknown, do NOT assign Low risk
        if not known_components:
            return {
                "risk_level": RISK_LEVEL_UNKNOWN,
                "risk_score": None,
                "risk_factors": ["No valid weather measurements available to calculate risk."],
                "risk_components": components,
                "risk_summary": "Weather observations unavailable; risk cannot be evaluated.",
                "data_quality": "unavailable",
            }

        # Sort known components by severity rank descending
        known_components.sort(key=lambda c: SEVERITY_RANK[c["risk_level"]], reverse=True)
        most_severe_comp = known_components[0]
        max_rank = SEVERITY_RANK[most_severe_comp["risk_level"]]

        # Requirement 8: If known components are all Low (rank 0), but some data is missing,
        # we cannot certify the checkpoint as Low risk!
        if max_rank == 0 and data_quality == "partial":
            risk_level = RISK_LEVEL_UNKNOWN
            risk_score = None
            risk_factors = [
                "Partial weather data: Available measurements are low, but missing variables "
                "prevent certifying Low risk."
            ]
            risk_summary = "Incomplete weather observations; cannot assign Low risk."
        else:
            risk_level = most_severe_comp["risk_level"]
            risk_score = most_severe_comp["score"]

            # Collect explanations for all elevated components (Moderate or worse)
            risk_factors = []
            for c in known_components:
                if SEVERITY_RANK[c["risk_level"]] >= 1:
                    risk_factors.append(c["reason"])

            if data_quality == "partial":
                missing_hazards = [h for h, c in components.items() if c["risk_level"] == RISK_LEVEL_UNKNOWN]
                risk_factors.append(f"Notice: Data unavailable for {', '.join(missing_hazards)}.")

            if risk_level == RISK_LEVEL_NO_TRAVEL:
                risk_summary = f"NO TRAVEL: {most_severe_comp['reason']}"
            elif risk_level == RISK_LEVEL_SEVERE:
                risk_summary = f"SEVERE HAZARD: {most_severe_comp['reason']}"
            elif risk_level == RISK_LEVEL_HIGH:
                risk_summary = f"HIGH RISK: {most_severe_comp['reason']}"
            elif risk_level == RISK_LEVEL_MODERATE:
                risk_summary = f"MODERATE RISK: {most_severe_comp['reason']}"
            else:
                risk_summary = "Favorable driving conditions; all observed hazards within low thresholds."

        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "risk_components": components,
            "risk_summary": risk_summary,
            "data_quality": data_quality,
        }

    def calculate_checkpoint_segment_distances(
        self,
        checkpoints: List[Dict[str, Any]],
        total_route_miles: float,
    ) -> List[float]:
        """
        Calculates the segment distance attributed to each checkpoint.
        Uses midpoint / voronoi attribution along the route checkpoints:
        - Checkpoint 1 (Departure) covers 0 to midpoint with checkpoint 2.
        - Checkpoint i covers midpoint(i-1, i) to midpoint(i, i+1).
        - Checkpoint N (Arrival) covers midpoint(N-1, N) to destination.
        The sum of segment distances equals total_route_miles.
        """
        n = len(checkpoints)
        if n == 0:
            return []
        if n == 1:
            return [round(total_route_miles, 2)]

        dists: List[float] = []
        for cp in checkpoints:
            d = cp.get("distance_from_origin_miles")
            dists.append(float(d if d is not None else 0.0))

        segment_miles: List[float] = []
        for i in range(n):
            if i == 0:
                len_i = (dists[1] - dists[0]) / 2.0
            elif i == n - 1:
                len_i = (dists[n - 1] - dists[n - 2]) / 2.0
            else:
                len_i = (dists[i + 1] - dists[i - 1]) / 2.0
            segment_miles.append(max(0.0, round(len_i, 2)))

        # Balance rounding drift to guarantee segment sum matches total_route_miles exactly
        sum_segs = sum(segment_miles)
        if sum_segs > 0 and total_route_miles > 0:
            drift = round(total_route_miles - sum_segs, 2)
            if abs(drift) > 0 and abs(drift) <= 1.0:
                max_idx = max(range(n), key=lambda idx: segment_miles[idx])
                segment_miles[max_idx] = round(segment_miles[max_idx] + drift, 2)

        return segment_miles

    def evaluate_route_risk(
        self,
        route_data: Dict[str, Any],
        load_weight_lb: float,
    ) -> Dict[str, Any]:
        """
        Assesses overall route risk by evaluating each checkpoint, attributing segment miles,
        calculating risk category mileages, and computing distance-weighted risk scores.
        """
        checkpoints = route_data.get("checkpoints", [])
        total_dist_miles = float(route_data.get("distance_miles") or 0.0)

        if not checkpoints:
            return {
                "overall_risk_level": RISK_LEVEL_UNKNOWN,
                "risk_score": None,
                "risk_factors": ["Route contains no checkpoints to evaluate."],
                "summary": "No checkpoints available for risk assessment.",
                "total_distance_miles": total_dist_miles,
                "low_risk_miles": 0.0,
                "moderate_risk_miles": 0.0,
                "high_risk_miles": 0.0,
                "severe_risk_miles": 0.0,
                "no_travel_miles": 0.0,
                "unknown_risk_miles": total_dist_miles,
                "no_travel_segments_count": 0,
                "no_travel_warning": False,
                "data_quality": "unavailable",
                "assumptions": self.DOCUMENTED_ASSUMPTIONS,
            }

        # 1. Evaluate risk for every checkpoint
        for cp in checkpoints:
            eval_result = self.evaluate_checkpoint_risk(cp, load_weight_lb)
            cp["risk_level"] = eval_result["risk_level"]
            cp["risk_score"] = eval_result["risk_score"]
            cp["risk_factors"] = eval_result["risk_factors"]
            cp["risk_components"] = eval_result["risk_components"]
            cp["risk_summary"] = eval_result["risk_summary"]
            cp["data_quality"] = eval_result["data_quality"]

        # 2. Calculate segment lengths
        segment_miles = self.calculate_checkpoint_segment_distances(checkpoints, total_dist_miles)

        # 3. Aggregate mileage per risk category
        category_miles: Dict[str, float] = {
            RISK_LEVEL_LOW: 0.0,
            RISK_LEVEL_MODERATE: 0.0,
            RISK_LEVEL_HIGH: 0.0,
            RISK_LEVEL_SEVERE: 0.0,
            RISK_LEVEL_NO_TRAVEL: 0.0,
            RISK_LEVEL_UNKNOWN: 0.0,
        }

        weighted_score_sum = 0.0
        scored_miles_sum = 0.0
        all_risk_factors: List[str] = []
        no_travel_count = 0

        for i, cp in enumerate(checkpoints):
            lvl = cp.get("risk_level", RISK_LEVEL_UNKNOWN)
            if lvl not in category_miles:
                lvl = RISK_LEVEL_UNKNOWN

            miles_i = segment_miles[i] if i < len(segment_miles) else 0.0
            category_miles[lvl] = round(category_miles[lvl] + miles_i, 2)

            score = cp.get("risk_score")
            if score is not None:
                weighted_score_sum += miles_i * float(score)
                scored_miles_sum += miles_i

            if lvl == RISK_LEVEL_NO_TRAVEL:
                no_travel_count += 1

            for factor in cp.get("risk_factors", []):
                if factor not in all_risk_factors:
                    all_risk_factors.append(factor)

        # Average risk score (distance-weighted)
        if scored_miles_sum > 0:
            avg_risk_score = round(weighted_score_sum / scored_miles_sum, 1)
        else:
            avg_risk_score = None

        # Determine overall route risk level (highest severity encountered)
        if category_miles[RISK_LEVEL_NO_TRAVEL] > 0 or no_travel_count > 0:
            overall_level = RISK_LEVEL_NO_TRAVEL
        elif category_miles[RISK_LEVEL_SEVERE] > 0:
            overall_level = RISK_LEVEL_SEVERE
        elif category_miles[RISK_LEVEL_HIGH] > 0:
            overall_level = RISK_LEVEL_HIGH
        elif category_miles[RISK_LEVEL_MODERATE] > 0:
            overall_level = RISK_LEVEL_MODERATE
        elif category_miles[RISK_LEVEL_LOW] > 0 and category_miles[RISK_LEVEL_UNKNOWN] == 0:
            overall_level = RISK_LEVEL_LOW
        else:
            overall_level = RISK_LEVEL_UNKNOWN

        # Route data quality
        total_unknown_miles = category_miles[RISK_LEVEL_UNKNOWN]
        if total_unknown_miles >= total_dist_miles:
            route_data_quality = "unavailable"
        elif total_unknown_miles > 0:
            route_data_quality = "partial"
        else:
            route_data_quality = "available"

        # Generate narrative route risk summary
        if overall_level == RISK_LEVEL_NO_TRAVEL:
            summary = (
                f"NO TRAVEL WARNING: Route encounters {category_miles[RISK_LEVEL_NO_TRAVEL]:.1f} miles of "
                f"extreme weather across {no_travel_count} segment(s). Commercial driving is unsafe and not advised."
            )
        elif overall_level == RISK_LEVEL_SEVERE:
            summary = (
                f"SEVERE RISK: Route encounters {category_miles[RISK_LEVEL_SEVERE]:.1f} severe weather miles "
                f"for load weight of {load_weight_lb:,.0f} lb. Extreme caution and reduced speeds required."
            )
        elif overall_level == RISK_LEVEL_HIGH:
            summary = (
                f"HIGH RISK: Route encounters {category_miles[RISK_LEVEL_HIGH]:.1f} high-risk weather miles. "
                "Significant caution advised."
            )
        elif overall_level == RISK_LEVEL_MODERATE:
            summary = (
                f"MODERATE RISK: Route encounters {category_miles[RISK_LEVEL_MODERATE]:.1f} moderate weather miles. "
                "Expect localized weather disruptions."
            )
        elif overall_level == RISK_LEVEL_LOW:
            summary = f"LOW RISK: Favorable driving conditions across all {total_dist_miles:.1f} miles."
        else:
            summary = "UNKNOWN RISK: Weather data is unavailable for route checkpoints; risk cannot be certified."

        return {
            "overall_risk_level": overall_level,
            "risk_score": avg_risk_score,
            "risk_factors": all_risk_factors,
            "summary": summary,
            "total_distance_miles": round(total_dist_miles, 1),
            "low_risk_miles": category_miles[RISK_LEVEL_LOW],
            "moderate_risk_miles": category_miles[RISK_LEVEL_MODERATE],
            "high_risk_miles": category_miles[RISK_LEVEL_HIGH],
            "severe_risk_miles": category_miles[RISK_LEVEL_SEVERE],
            "no_travel_miles": category_miles[RISK_LEVEL_NO_TRAVEL],
            "unknown_risk_miles": category_miles[RISK_LEVEL_UNKNOWN],
            "no_travel_segments_count": no_travel_count,
            "no_travel_warning": (no_travel_count > 0),
            "data_quality": route_data_quality,
            "assumptions": self.DOCUMENTED_ASSUMPTIONS,
        }

    def attach_risk_to_routes(
        self,
        routes: List[Dict[str, Any]],
        load_weight_lb: float,
    ) -> List[Dict[str, Any]]:
        """
        Attaches comprehensive risk assessments to each route option and updates checkpoints in-place.
        """
        for route in routes:
            assessment = self.evaluate_route_risk(route, load_weight_lb)
            route["risk_assessment"] = assessment
        return routes
