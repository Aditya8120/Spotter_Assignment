"""
Serializers for Route Planning requests and responses.
"""
from datetime import datetime
from typing import Any, Dict, Tuple
from rest_framework import serializers


class LocationField(serializers.Field):
    """
    Serializer field that accepts either location text (e.g., 'Chicago, IL')
    or coordinates (e.g., {'latitude': 41.8781, 'longitude': -87.6298}, [41.8781, -87.6298], or '41.8781, -87.6298').
    """

    def to_internal_value(self, data: Any) -> Dict[str, Any]:
        if data is None:
            raise serializers.ValidationError("Location cannot be null.")

        # Coordinate Dictionary
        if isinstance(data, dict):
            lat = data.get('latitude') if 'latitude' in data else data.get('lat')
            lon = data.get('longitude') if 'longitude' in data else (data.get('lon') if 'lon' in data else data.get('lng'))

            if lat is None or lon is None:
                text_query = data.get('address') or data.get('name') or data.get('text')
                if text_query and isinstance(text_query, str) and text_query.strip():
                    return {"type": "text", "query": text_query.strip()}
                raise serializers.ValidationError(
                    "Coordinate object must contain 'latitude' and 'longitude' (or 'lat' and 'lon'/'lng')."
                )

            lat_val, lon_val = self._validate_coordinates(lat, lon)
            return {
                "type": "coordinates",
                "latitude": lat_val,
                "longitude": lon_val,
                "label": data.get('label') or f"{lat_val}, {lon_val}",
            }

        # Coordinate list or tuple [lat, lon]
        if isinstance(data, (list, tuple)):
            if len(data) != 2:
                raise serializers.ValidationError(
                    "Coordinate list must contain exactly two numbers: [latitude, longitude]."
                )
            lat_val, lon_val = self._validate_coordinates(data[0], data[1])
            return {
                "type": "coordinates",
                "latitude": lat_val,
                "longitude": lon_val,
                "label": f"{lat_val}, {lon_val}",
            }

        # Text string or comma-separated coordinates
        if isinstance(data, str):
            cleaned = data.strip()
            if not cleaned:
                raise serializers.ValidationError("Location cannot be blank or empty.")

            # Check if formatted as comma-separated numeric coordinates
            parts = [p.strip() for p in cleaned.split(',')]
            if len(parts) == 2:
                try:
                    lat_num = float(parts[0])
                    lon_num = float(parts[1])
                    lat_val, lon_val = self._validate_coordinates(lat_num, lon_num)
                    return {
                        "type": "coordinates",
                        "latitude": lat_val,
                        "longitude": lon_val,
                        "label": cleaned,
                    }
                except serializers.ValidationError:
                    raise
                except (ValueError, TypeError):
                    # Comma separated but not numeric (e.g., "Chicago, IL") -> treat as text
                    pass

            return {
                "type": "text",
                "query": cleaned,
            }

        raise serializers.ValidationError(
            "Location must be a text string or a coordinates object."
        )

    def _validate_coordinates(self, lat: Any, lon: Any) -> Tuple[float, float]:
        try:
            lat_float = float(lat)
            lon_float = float(lon)
        except (ValueError, TypeError):
            raise serializers.ValidationError("Latitude and longitude must be valid numeric values.")

        if not (-90.0 <= lat_float <= 90.0):
            raise serializers.ValidationError(
                f"Latitude must be between -90 and 90 degrees. Received: {lat_float}."
            )
        if not (-180.0 <= lon_float <= 180.0):
            raise serializers.ValidationError(
                f"Longitude must be between -180 and 180 degrees. Received: {lon_float}."
            )

        return round(lat_float, 6), round(lon_float, 6)

    def to_representation(self, value: Any) -> Any:
        if isinstance(value, dict):
            if value.get("type") == "coordinates":
                return {
                    "latitude": value.get("latitude"),
                    "longitude": value.get("longitude"),
                }
            if value.get("type") == "text":
                return value.get("query")
        return value


class RoutePlanRequestSerializer(serializers.Serializer):
    """
    Validates route planning request payloads.
    """
    origin = LocationField(
        required=True,
        error_messages={
            'required': 'Origin location is required.',
            'null': 'Origin location cannot be null.',
        }
    )
    destination = LocationField(
        required=True,
        error_messages={
            'required': 'Destination location is required.',
            'null': 'Destination location cannot be null.',
        }
    )
    departure_datetime = serializers.DateTimeField(
        required=True,
        error_messages={
            'required': 'Departure date and time (departure_datetime) is required.',
            'invalid': 'Invalid date/time format. Provide a valid ISO 8601 string (e.g. 2026-10-30T08:00:00Z).',
            'null': 'Departure date and time cannot be null.',
        }
    )
    load_weight_lb = serializers.FloatField(
        required=True,
        error_messages={
            'required': 'Truck load weight (load_weight_lb) is required.',
            'invalid': 'Load weight must be a valid numeric value in pounds.',
            'null': 'Load weight cannot be null.',
        }
    )
    checkpoint_interval_miles = serializers.IntegerField(
        required=False,
        default=25,
        error_messages={
            'invalid': 'Checkpoint interval must be a valid integer in miles (10, 25, or 50).',
        }
    )

    def validate_load_weight_lb(self, value: float) -> float:
        if value <= 0:
            raise serializers.ValidationError(
                "Load weight must be a positive number greater than 0 pounds."
            )
        if value > 250000:
            raise serializers.ValidationError(
                "Load weight exceeds maximum realistic limit of 250,000 lbs."
            )
        return float(value)

    def validate_checkpoint_interval_miles(self, value: int) -> int:
        if value not in (10, 25, 50):
            raise serializers.ValidationError(
                "Checkpoint interval must be 10, 25, or 50 miles."
            )
        return int(value)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        origin = attrs.get('origin')
        destination = attrs.get('destination')

        if origin and destination:
            # Check identical text queries
            if origin.get('type') == 'text' and destination.get('type') == 'text':
                if origin.get('query', '').strip().lower() == destination.get('query', '').strip().lower():
                    raise serializers.ValidationError({
                        "destination": "Destination location cannot be identical to origin."
                    })
            # Check identical coordinates
            if origin.get('type') == 'coordinates' and destination.get('type') == 'coordinates':
                if (origin.get('latitude') == destination.get('latitude') and
                        origin.get('longitude') == destination.get('longitude')):
                    raise serializers.ValidationError({
                        "destination": "Destination coordinates cannot be identical to origin coordinates."
                    })

        return attrs


# -------------------------------------------------------------------------
# Response Schemas (Consistent structure for up to 3 route options)
# -------------------------------------------------------------------------

class WeatherObservationSerializer(serializers.Serializer):
    """Weather observations and units at a route checkpoint."""
    timestamp = serializers.DateTimeField(allow_null=True, required=False)
    forecast_timestamp = serializers.DateTimeField(allow_null=True, required=False)
    data_availability = serializers.ChoiceField(
        choices=['available', 'partial', 'unavailable', 'out_of_forecast_horizon'],
        default='unavailable'
    )
    temperature = serializers.FloatField(allow_null=True, required=False)
    condition = serializers.CharField(allow_null=True, required=False)
    weather_code = serializers.IntegerField(allow_null=True, required=False)
    wind_speed_mph = serializers.FloatField(allow_null=True, required=False)
    wind_gust_mph = serializers.FloatField(allow_null=True, required=False)
    precipitation_probability = serializers.FloatField(allow_null=True, required=False)
    precipitation_in_per_hour = serializers.FloatField(allow_null=True, required=False)
    snowfall_in_per_hour = serializers.FloatField(allow_null=True, required=False)
    precipitation_rate_in_per_hour = serializers.FloatField(allow_null=True, required=False)
    snowfall_rate_in_per_hour = serializers.FloatField(allow_null=True, required=False)
    precipitation_accumulation_in = serializers.FloatField(allow_null=True, required=False)
    snowfall_accumulation_in = serializers.FloatField(allow_null=True, required=False)
    visibility_miles = serializers.FloatField(allow_null=True, required=False)
    notes = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    limitations = serializers.ListField(
        child=serializers.CharField(),
        default=list,
        required=False
    )
    units = serializers.DictField(
        default=lambda: {
            "temperature": "°F",
            "wind_speed": "mph",
            "wind_gust": "mph",
            "precipitation": "in/h",
            "snowfall": "in/h",
            "precipitation_probability": "%",
            "visibility": "miles",
        },
        required=False
    )


class CheckpointSerializer(serializers.Serializer):
    """An ordered waypoint or checkpoint along a route."""
    sequence = serializers.IntegerField(min_value=1)
    name = serializers.CharField(allow_null=True, required=False)
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    estimated_arrival = serializers.DateTimeField(allow_null=True, required=False)
    distance_from_origin_miles = serializers.FloatField(allow_null=True, required=False)
    distance_from_origin_km = serializers.FloatField(allow_null=True, required=False)
    duration_from_origin_seconds = serializers.IntegerField(allow_null=True, required=False)
    weather = WeatherObservationSerializer(allow_null=True, required=False)
    risk_level = serializers.ChoiceField(
        choices=['low', 'moderate', 'high', 'severe', 'unknown'],
        default='unknown'
    )
    risk_summary = serializers.CharField(allow_null=True, required=False)


class RouteRecommendationSerializer(serializers.Serializer):
    """Route recommendation status and explanation."""
    is_recommended = serializers.BooleanField(default=False)
    status = serializers.ChoiceField(
        choices=['recommended', 'viable_alternative', 'not_recommended', 'pending'],
        default='pending'
    )
    explanation = serializers.CharField(allow_blank=True)


class RiskAssessmentSerializer(serializers.Serializer):
    """Overall route risk score, level, and hazard factors."""
    overall_risk_level = serializers.ChoiceField(
        choices=['low', 'moderate', 'high', 'severe', 'unknown'],
        default='unknown'
    )
    risk_score = serializers.FloatField(allow_null=True, required=False)
    risk_factors = serializers.ListField(
        child=serializers.CharField(),
        default=list
    )
    summary = serializers.CharField(allow_blank=True)


class RouteOptionSerializer(serializers.Serializer):
    """Representation of an individual route option (up to 3 per response)."""
    route_id = serializers.CharField()
    display_name = serializers.CharField()
    distance_miles = serializers.FloatField(allow_null=True, required=False)
    distance_km = serializers.FloatField(allow_null=True, required=False)
    duration_seconds = serializers.IntegerField(allow_null=True)
    duration_formatted = serializers.CharField(allow_null=True, required=False)
    geometry = serializers.DictField(allow_null=True, required=False)
    checkpoints = CheckpointSerializer(many=True, default=list)
    weather_summary = serializers.DictField(allow_null=True, required=False)
    risk_assessment = RiskAssessmentSerializer(allow_null=True, required=False)
    recommendation = RouteRecommendationSerializer()



class RequestSummarySerializer(serializers.Serializer):
    """Normalized summary of the parsed route-planning request."""
    origin = LocationField()
    destination = LocationField()
    departure_datetime = serializers.DateTimeField()
    load_weight_lb = serializers.FloatField()
    checkpoint_interval_miles = serializers.IntegerField(default=25, required=False)


class RoutePlanResponseSerializer(serializers.Serializer):
    """Top-level response contract for route planning."""
    status = serializers.CharField(default="not_implemented")
    message = serializers.CharField()
    request_summary = RequestSummarySerializer()
    routes = RouteOptionSerializer(many=True, default=list)

    def validate_routes(self, routes: list) -> list:
        if len(routes) > 3:
            raise serializers.ValidationError("A maximum of 3 route options may be returned.")
        return routes

