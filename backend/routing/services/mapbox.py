"""
Mapbox Directions API service module.
Handles geocoding, route calculation, response parsing, and error mapping.
Never logs or exposes tokens in error messages.
"""
from datetime import datetime, timedelta
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import requests

from .route_engine import BaseRouteEngine

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Exceptions
# -------------------------------------------------------------------------

class MapboxServiceError(Exception):
    """Base exception for Mapbox service errors."""
    pass


class MapboxConfigurationError(MapboxServiceError):
    """Raised when Mapbox access token is missing or unconfigured."""
    pass


class MapboxAuthenticationError(MapboxServiceError):
    """Raised when the Mapbox token is rejected (HTTP 401/403)."""
    pass


class MapboxRateLimitError(MapboxServiceError):
    """Raised when Mapbox API rate limit is reached (HTTP 429)."""
    pass


class MapboxTimeoutError(MapboxServiceError):
    """Raised when the request to Mapbox times out."""
    pass


class MapboxConnectionError(MapboxServiceError):
    """Raised when network connection to Mapbox fails."""
    pass


class MapboxNoRouteError(MapboxServiceError):
    """Raised when no route can be found between coordinates."""
    pass


class MapboxGeocodingError(MapboxServiceError):
    """Raised when a location text query cannot be resolved to coordinates."""
    pass


# -------------------------------------------------------------------------
# Service Implementation
# -------------------------------------------------------------------------

class MapboxRoutingService(BaseRouteEngine):
    """
    Integrates with Mapbox Directions and Geocoding APIs.
    Translates Mapbox responses into our standardized RouteOption representations.
    """

    DIRECTIONS_BASE_URL = "https://api.mapbox.com/directions/v5/mapbox/driving"
    GEOCODING_BASE_URL = "https://api.mapbox.com/geocoding/v5/mapbox.places"
    DEFAULT_TIMEOUT_SECONDS = 10.0

    def __init__(self, token: Optional[str] = None):
        self._token = token or os.environ.get("MAPBOX_ACCESS_TOKEN", "").strip()

    def _get_token(self) -> str:
        if not self._token:
            raise MapboxConfigurationError(
                "Mapbox access token is not configured. Set MAPBOX_ACCESS_TOKEN in environment."
            )
        return self._token

    def resolve_coordinates(self, location: Dict[str, Any]) -> Tuple[float, float, str]:
        """
        Resolves a location payload (coordinates dict or text query) into (latitude, longitude, label).
        """
        loc_type = location.get("type")
        if loc_type == "coordinates":
            lat = float(location["latitude"])
            lon = float(location["longitude"])
            label = location.get("label") or f"{lat}, {lon}"
            return lat, lon, label

        if loc_type == "text":
            query = location.get("query", "").strip()
            return self.geocode_text(query)

        raise MapboxGeocodingError("Unsupported location format.")

    def geocode_text(self, query: str) -> Tuple[float, float, str]:
        """
        Calls Mapbox Geocoding API to obtain coordinates for a text query.
        """
        token = self._get_token()
        if not query:
            raise MapboxGeocodingError("Location text cannot be empty.")

        url = f"{self.GEOCODING_BASE_URL}/{requests.utils.quote(query)}.json"
        params = {
            "access_token": token,
            "limit": 1,
        }

        try:
            response = requests.get(url, params=params, timeout=self.DEFAULT_TIMEOUT_SECONDS)
        except requests.exceptions.Timeout:
            raise MapboxTimeoutError("Geocoding request timed out.")
        except requests.exceptions.ConnectionError:
            raise MapboxConnectionError("Network error while connecting to geocoding provider.")
        except requests.exceptions.RequestException as exc:
            raise MapboxServiceError(f"Geocoding request failed: {exc}")

        if response.status_code in (401, 403):
            raise MapboxAuthenticationError("Invalid or unauthorized Mapbox access token.")
        if response.status_code == 429:
            raise MapboxRateLimitError("Geocoding provider rate limit exceeded.")
        if not response.ok:
            raise MapboxServiceError("Geocoding service returned an unexpected error.")

        data = response.json()
        features = data.get("features", [])
        if not features:
            raise MapboxGeocodingError(f"Could not find coordinates for location: '{query}'.")

        best_match = features[0]
        center = best_match.get("center")  # [longitude, latitude]
        if not center or len(center) < 2:
            raise MapboxGeocodingError(f"Invalid coordinate payload returned for: '{query}'.")

        lon, lat = float(center[0]), float(center[1])
        place_name = best_match.get("place_name", query)
        return lat, lon, place_name

    def get_directions(
        self,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
    ) -> List[Dict[str, Any]]:
        """
        Fetches driving directions from Mapbox Directions API v5.
        Requests alternatives where supported. Returns raw Mapbox routes.
        """
        token = self._get_token()
        # Mapbox expects {longitude},{latitude};{longitude},{latitude}
        coords_str = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        url = f"{self.DIRECTIONS_BASE_URL}/{coords_str}"
        params = {
            "alternatives": "true",
            "geometries": "geojson",
            "overview": "full",
            "steps": "true",
            "access_token": token,
        }

        try:
            response = requests.get(url, params=params, timeout=self.DEFAULT_TIMEOUT_SECONDS)
        except requests.exceptions.Timeout:
            raise MapboxTimeoutError("Routing request timed out.")
        except requests.exceptions.ConnectionError:
            raise MapboxConnectionError("Network connection error to routing provider.")
        except requests.exceptions.RequestException as exc:
            raise MapboxServiceError(f"Routing request error: {exc}")

        if response.status_code in (401, 403):
            raise MapboxAuthenticationError("Invalid or unauthorized Mapbox access token.")
        if response.status_code == 429:
            raise MapboxRateLimitError("Routing provider rate limit exceeded.")

        if not response.ok:
            try:
                err_body = response.json()
                code = err_body.get("code")
                if code == "NoRoute":
                    raise MapboxNoRouteError("No driving route found between specified coordinates.")
            except (ValueError, KeyError):
                pass
            raise MapboxServiceError(f"Routing provider returned HTTP {response.status_code}.")

        data = response.json()
        code = data.get("code")
        if code != "Ok":
            if code == "NoRoute":
                raise MapboxNoRouteError("No driving route found between specified coordinates.")
            message = data.get("message", "Provider returned error.")
            raise MapboxServiceError(f"Provider routing failure: {message}")

        routes = data.get("routes", [])
        if not routes:
            raise MapboxNoRouteError("No route options returned by provider.")

        # Return up to three distinct routes
        return routes[:3]

    def calculate_routes(
        self,
        origin: Dict[str, Any],
        destination: Dict[str, Any],
        departure_datetime: Any,
        load_weight_lb: float,
    ) -> List[Dict[str, Any]]:
        """
        Main interface method. Resolves locations, calls Mapbox, and formats response.
        """
        if isinstance(departure_datetime, str):
            departure_datetime = datetime.fromisoformat(departure_datetime.replace('Z', '+00:00'))

        origin_lat, origin_lon, origin_label = self.resolve_coordinates(origin)
        dest_lat, dest_lon, dest_label = self.resolve_coordinates(destination)


        raw_routes = self.get_directions(origin_lat, origin_lon, dest_lat, dest_lon)

        formatted_routes: List[Dict[str, Any]] = []

        for idx, route in enumerate(raw_routes):
            route_id = f"mapbox-route-{idx + 1}"
            dist_meters = float(route.get("distance", 0.0))
            dur_seconds = int(round(float(route.get("duration", 0.0))))

            dist_miles = round(dist_meters * 0.000621371, 1)
            dist_km = round(dist_meters / 1000.0, 1)
            dur_formatted = self._format_duration(dur_seconds)

            # Route summary name
            legs = route.get("legs", [])
            summary = legs[0].get("summary", "") if legs else ""
            if idx == 0:
                display_name = f"Primary Route (via {summary})" if summary else "Primary Route"
                recommendation = {
                    "is_recommended": True,
                    "status": "recommended",
                    "explanation": (
                        "Primary route recommended by Mapbox based on shortest duration and road classification. "
                        "Note: Reflects standard passenger driving profile; truck height/weight limits and "
                        "weather conditions are not yet accounted for."
                    ),
                }
            else:
                display_name = f"Alternative {idx} (via {summary})" if summary else f"Alternative Route {idx}"
                recommendation = {
                    "is_recommended": False,
                    "status": "viable_alternative",
                    "explanation": (
                        f"Viable alternative route option via {summary or 'secondary corridor'}. "
                        "Note: Standard road routing; truck restrictions and weather hazards not yet evaluated."
                    ),
                }

            # Extract ordered checkpoints
            checkpoints = self._build_checkpoints(
                legs=legs,
                origin_lat=origin_lat,
                origin_lon=origin_lon,
                origin_label=origin_label,
                dest_lat=dest_lat,
                dest_lon=dest_lon,
                dest_label=dest_label,
                departure_dt=departure_datetime,
                total_duration_sec=dur_seconds,
                total_dist_meters=dist_meters,
            )

            formatted_routes.append({
                "route_id": route_id,
                "display_name": display_name,
                "distance_miles": dist_miles,
                "distance_km": dist_km,
                "duration_seconds": dur_seconds,
                "duration_formatted": dur_formatted,
                "geometry": route.get("geometry"),
                "checkpoints": checkpoints,
                "weather_summary": {},
                "risk_assessment": {
                    "overall_risk_level": "unknown",
                    "risk_score": None,
                    "risk_factors": [],
                    "summary": "Weather hazard risk scoring is not yet integrated.",
                },
                "recommendation": recommendation,
            })

        return formatted_routes

    def _build_checkpoints(
        self,
        legs: List[Dict[str, Any]],
        origin_lat: float,
        origin_lon: float,
        origin_label: str,
        dest_lat: float,
        dest_lon: float,
        dest_label: str,
        departure_dt: datetime,
        total_duration_sec: int,
        total_dist_meters: float,
    ) -> List[Dict[str, Any]]:
        """
        Builds an ordered sequence of route checkpoints from legs and maneuvers.
        """
        checkpoints: List[Dict[str, Any]] = []

        # 1. Origin Checkpoint
        checkpoints.append({
            "sequence": 1,
            "name": f"Departure: {origin_label}",
            "latitude": origin_lat,
            "longitude": origin_lon,
            "estimated_arrival": departure_dt.isoformat(),
            "distance_from_origin_miles": 0.0,
            "distance_from_origin_km": 0.0,
            "duration_from_origin_seconds": 0,
            "weather": None,
            "risk_level": "unknown",
            "risk_summary": None,
        })

        # 2. Intermediate Waypoints (Sampled from key steps)
        cum_dist_meters = 0.0
        cum_dur_seconds = 0.0

        all_steps = []
        for leg in legs:
            for step in leg.get("steps", []):
                all_steps.append(step)

        # To keep checkpoint list clean and useful for weather sampling (aim for 5-15 checkpoints):
        if len(all_steps) > 2:
            step_stride = max(1, len(all_steps) // 8)
            seq_num = 2

            for i, step in enumerate(all_steps[1:-1], start=1):
                cum_dist_meters += float(step.get("distance", 0.0))
                cum_dur_seconds += float(step.get("duration", 0.0))

                if i % step_stride == 0:
                    maneuver = step.get("maneuver", {})
                    loc = maneuver.get("location")  # [lon, lat]
                    if loc and len(loc) >= 2:
                        step_lon, step_lat = float(loc[0]), float(loc[1])
                        name = step.get("name") or maneuver.get("instruction") or f"Waypoint {seq_num - 1}"
                        arrival_dt = departure_dt + timedelta(seconds=int(cum_dur_seconds))

                        checkpoints.append({
                            "sequence": seq_num,
                            "name": name,
                            "latitude": round(step_lat, 6),
                            "longitude": round(step_lon, 6),
                            "estimated_arrival": arrival_dt.isoformat(),
                            "distance_from_origin_miles": round(cum_dist_meters * 0.000621371, 1),
                            "distance_from_origin_km": round(cum_dist_meters / 1000.0, 1),
                            "duration_from_origin_seconds": int(round(cum_dur_seconds)),
                            "weather": None,
                            "risk_level": "unknown",
                            "risk_summary": None,
                        })
                        seq_num += 1

        # 3. Final Destination Checkpoint
        final_arrival_dt = departure_dt + timedelta(seconds=total_duration_sec)
        checkpoints.append({
            "sequence": len(checkpoints) + 1,
            "name": f"Arrival: {dest_label}",
            "latitude": dest_lat,
            "longitude": dest_lon,
            "estimated_arrival": final_arrival_dt.isoformat(),
            "distance_from_origin_miles": round(total_dist_meters * 0.000621371, 1),
            "distance_from_origin_km": round(total_dist_meters / 1000.0, 1),
            "duration_from_origin_seconds": total_duration_sec,
            "weather": None,
            "risk_level": "unknown",
            "risk_summary": None,
        })

        return checkpoints

    @staticmethod
    def _format_duration(seconds: int) -> str:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"
