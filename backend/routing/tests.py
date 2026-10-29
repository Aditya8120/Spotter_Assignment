from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import json
from unittest.mock import MagicMock, patch
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
import requests

from .serializers import (
    RoutePlanRequestSerializer,
    RoutePlanResponseSerializer,
)
from .services import (
    MapboxRoutingService,
    MapboxConfigurationError,
    MapboxAuthenticationError,
    MapboxRateLimitError,
    MapboxTimeoutError,
    MapboxConnectionError,
    MapboxNoRouteError,
    MapboxGeocodingError,
    OpenMeteoWeatherService,
    WeatherServiceError,
    WeatherProviderError,
    WeatherTimeoutError,
    WeatherConnectionError,
    WeatherRateLimitError,
    WeatherRiskService,
    RISK_LEVEL_LOW,
    RISK_LEVEL_MODERATE,
    RISK_LEVEL_HIGH,
    RISK_LEVEL_SEVERE,
    RISK_LEVEL_NO_TRAVEL,
    RISK_LEVEL_UNKNOWN,
    RouteRecommendationService,
    STATUS_RECOMMENDED,
    STATUS_VIABLE_ALTERNATIVE,
    STATUS_NOT_RECOMMENDED,
    ELIGIBILITY_ELIGIBLE,
    ELIGIBILITY_NO_TRAVEL,
    ELIGIBILITY_INCOMPLETE,
    ASSESSMENT_COMPLETE,
    ASSESSMENT_PARTIAL,
    ASSESSMENT_UNAVAILABLE,
)
from django.test import SimpleTestCase


def mock_open_meteo_forecast(
    base_time="2026-10-30T00:00",
    num_hours=72,
    wind_speed=15.5,
    wind_gust=22.0,
    precip=0.25,
    snow=0.10,
    temp=38.0,
    weather_code=61,
    precip_prob=40.0,
):
    """Helper creating a realistic Open-Meteo hourly forecast fixture."""
    base_dt = datetime.fromisoformat(base_time)
    times = [(base_dt + timedelta(hours=i)).isoformat()[:16] for i in range(num_hours)]
    return {
        "latitude": 41.8781,
        "longitude": -87.6298,
        "elevation": 180.0,
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m": "°F",
            "precipitation_probability": "%",
            "precipitation": "inch",
            "snowfall": "inch",
            "weather_code": "wmo code",
            "wind_speed_10m": "mph",
            "wind_gusts_10m": "mph",
        },
        "hourly": {
            "time": times,
            "temperature_2m": [temp] * num_hours,
            "precipitation_probability": [precip_prob] * num_hours,
            "precipitation": [precip] * num_hours,
            "snowfall": [snow] * num_hours,
            "weather_code": [weather_code] * num_hours,
            "wind_speed_10m": [wind_speed] * num_hours,
            "wind_gusts_10m": [wind_gust] * num_hours,
        }
    }


def mock_mapbox_route(distance_m=1488000.0, duration_s=50400.0, summary="I-55 S, I-30 W"):
    """Helper creating a realistic Mapbox Directions route fixture."""
    return {
        "distance": distance_m,
        "duration": duration_s,
        "geometry": {
            "type": "LineString",
            "coordinates": [[-87.6298, 41.8781], [-90.1994, 38.6270], [-96.7970, 32.7767]]
        },
        "legs": [
            {
                "distance": distance_m,
                "duration": duration_s,
                "summary": summary,
                "steps": [
                    {
                        "distance": 500000.0,
                        "duration": 18000.0,
                        "name": "I-55 S",
                        "maneuver": {
                            "location": [-87.6298, 41.8781],
                            "instruction": "Depart south on I-55 S"
                        }
                    },
                    {
                        "distance": 488000.0,
                        "duration": 16400.0,
                        "name": "I-30 W",
                        "maneuver": {
                            "location": [-90.1994, 38.6270],
                            "instruction": "Merge onto I-30 W"
                        }
                    },
                    {
                        "distance": 500000.0,
                        "duration": 16000.0,
                        "name": "Commerce St",
                        "maneuver": {
                            "location": [-96.7970, 32.7767],
                            "instruction": "Arrive at destination"
                        }
                    }
                ]
            }
        ]
    }


def mock_geocoding_feature(lat=41.8781, lon=-87.6298, place_name="Chicago, Illinois, United States"):
    """Helper creating a realistic Mapbox Geocoding feature fixture."""
    return {
        "features": [
            {
                "center": [lon, lat],
                "place_name": place_name,
            }
        ]
    }


class HealthCheckTests(APITestCase):
    def test_health_check_returns_ok(self):
        url = reverse('health_check')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("application/json", response["Content-Type"])

    def test_cors_allowed_for_vite_frontend(self):
        url = reverse('health_check')
        response = self.client.get(url, HTTP_ORIGIN="http://localhost:5173")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get("Access-Control-Allow-Origin"), "http://localhost:5173")

    def test_cors_disallowed_for_unauthorized_origin(self):
        url = reverse('health_check')
        response = self.client.get(url, HTTP_ORIGIN="http://unauthorized-domain.com")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.get("Access-Control-Allow-Origin"))


class RouteRequestValidationTests(APITestCase):
    """Verifies that invalid requests are caught by DRF serializers before calling the provider."""
    def setUp(self):
        self.url = reverse('plan_routes')
        self.valid_payload = {
            "origin": {"latitude": 41.8781, "longitude": -87.6298},
            "destination": {"latitude": 32.7767, "longitude": -96.7970},
            "departure_datetime": "2026-10-30T08:00:00Z",
            "load_weight_lb": 35000.0,
        }

    def test_missing_origin(self):
        payload = dict(self.valid_payload)
        del payload["origin"]
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("origin", response.json())

    def test_missing_destination(self):
        payload = dict(self.valid_payload)
        del payload["destination"]
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("destination", response.json())

    def test_blank_origin_string(self):
        payload = dict(self.valid_payload, origin="   ")
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("origin", response.json())

    def test_missing_departure_datetime(self):
        payload = dict(self.valid_payload)
        del payload["departure_datetime"]
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("departure_datetime", response.json())

    def test_invalid_departure_datetime(self):
        payload = dict(self.valid_payload, departure_datetime="invalid-date-format")
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("departure_datetime", response.json())

    def test_missing_load_weight(self):
        payload = dict(self.valid_payload)
        del payload["load_weight_lb"]
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("load_weight_lb", response.json())

    def test_zero_load_weight_rejected(self):
        payload = dict(self.valid_payload, load_weight_lb=0)
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("load_weight_lb", response.json())

    def test_negative_load_weight_rejected(self):
        payload = dict(self.valid_payload, load_weight_lb=-1500.0)
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("load_weight_lb", response.json())

    def test_invalid_coordinates_out_of_range(self):
        payload = dict(self.valid_payload, origin={"latitude": 95.0, "longitude": -87.0})
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("origin", response.json())

    def test_identical_origin_and_destination(self):
        payload = dict(self.valid_payload, origin="Chicago, IL", destination="Chicago, IL")
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("destination", response.json())


class MapboxServiceUnitTests(APITestCase):
    """Direct unit tests for the MapboxRoutingService module."""

    def test_missing_token_raises_configuration_error(self):
        service = MapboxRoutingService(token="")
        with self.assertRaises(MapboxConfigurationError):
            service.geocode_text("Chicago, IL")

    @patch('requests.get')
    def test_geocode_text_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_geocoding_feature(41.8781, -87.6298, "Chicago, IL")
        mock_get.return_value = mock_resp

        service = MapboxRoutingService(token="pk.mock-test-token")
        lat, lon, label = service.geocode_text("Chicago, IL")
        self.assertEqual(lat, 41.8781)
        self.assertEqual(lon, -87.6298)
        self.assertEqual(label, "Chicago, IL")

    @patch('requests.get')
    def test_geocode_no_results_raises_geocoding_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"features": []}
        mock_get.return_value = mock_resp

        service = MapboxRoutingService(token="pk.mock-test-token")
        with self.assertRaises(MapboxGeocodingError):
            service.geocode_text("NonExistentUnknownPlace12345XYZ")

    @patch('requests.get')
    def test_directions_auth_error_raises_auth_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        service = MapboxRoutingService(token="pk.invalid-token")
        with self.assertRaises(MapboxAuthenticationError):
            service.get_directions(41.8781, -87.6298, 32.7767, -96.7970)

    @patch('requests.get')
    def test_directions_rate_limit_raises_rate_limit_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp

        service = MapboxRoutingService(token="pk.mock-test-token")
        with self.assertRaises(MapboxRateLimitError):
            service.get_directions(41.8781, -87.6298, 32.7767, -96.7970)

    @patch('requests.get')
    def test_directions_no_route_raises_no_route_error(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"code": "NoRoute", "routes": []}
        mock_get.return_value = mock_resp

        service = MapboxRoutingService(token="pk.mock-test-token")
        with self.assertRaises(MapboxNoRouteError):
            service.get_directions(41.8781, -87.6298, 32.7767, -96.7970)

    @patch('requests.get')
    def test_directions_timeout_raises_timeout_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Request timed out")

        service = MapboxRoutingService(token="pk.mock-test-token")
        with self.assertRaises(MapboxTimeoutError):
            service.get_directions(41.8781, -87.6298, 32.7767, -96.7970)

    @patch('requests.get')
    def test_directions_connection_error_raises_connection_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        service = MapboxRoutingService(token="pk.mock-test-token")
        with self.assertRaises(MapboxConnectionError):
            service.get_directions(41.8781, -87.6298, 32.7767, -96.7970)


class RoutePlanningAPIWithMapboxTests(APITestCase):
    """Integration tests for POST /api/routes/ using mocked Mapbox responses."""

    def setUp(self):
        self.url = reverse('plan_routes')
        self.valid_payload = {
            "origin": {"latitude": 41.8781, "longitude": -87.6298},
            "destination": {"latitude": 32.7767, "longitude": -96.7970},
            "departure_datetime": "2026-10-30T08:00:00Z",
            "load_weight_lb": 35000.0,
        }

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': ''}, clear=False)
    def test_missing_mapbox_token_returns_503(self):
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["code"], "provider_not_configured")
        self.assertIn("MAPBOX_ACCESS_TOKEN", data["message"])

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token-for-test'})
    @patch('requests.get')
    def test_successful_routing_three_alternatives(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": "Ok",
            "routes": [
                mock_mapbox_route(1488000.0, 50400.0, "I-55 S, I-30 W"),
                mock_mapbox_route(1520000.0, 52000.0, "I-57 S, I-40 W"),
                mock_mapbox_route(1590000.0, 54500.0, "I-70 W, I-44 W"),
            ]
        }
        mock_get.return_value = mock_resp

        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["status"], "planned")
        self.assertIn("request_summary", data)
        self.assertEqual(len(data["routes"]), 3)

        # Primary route assertions
        primary = data["routes"][0]
        self.assertEqual(primary["route_id"], "mapbox-route-1")
        self.assertTrue(primary["recommendation"]["is_recommended"])
        self.assertEqual(primary["recommendation"]["status"], "recommended")
        self.assertIn("geometry", primary)
        self.assertEqual(primary["geometry"]["type"], "LineString")
        self.assertGreater(primary["distance_km"], 1000.0)
        self.assertGreater(primary["distance_miles"], 600.0)
        self.assertEqual(primary["duration_seconds"], 50400)
        self.assertEqual(primary["duration_formatted"], "14h 0m")
        self.assertGreaterEqual(len(primary["checkpoints"]), 2)

        # Alternatives assertions
        alt1 = data["routes"][1]
        self.assertEqual(alt1["route_id"], "mapbox-route-2")
        self.assertFalse(alt1["recommendation"]["is_recommended"])
        self.assertEqual(alt1["recommendation"]["status"], "viable_alternative")

        alt2 = data["routes"][2]
        self.assertEqual(alt2["route_id"], "mapbox-route-3")
        self.assertFalse(alt2["recommendation"]["is_recommended"])

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token-for-test'})
    @patch('requests.get')
    def test_successful_routing_single_route_no_fabricated_alternatives(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": "Ok",
            "routes": [
                mock_mapbox_route(1488000.0, 50400.0, "I-55 S"),
            ]
        }
        mock_get.return_value = mock_resp

        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "planned")
        self.assertEqual(len(data["routes"]), 1)
        self.assertEqual(data["routes"][0]["route_id"], "mapbox-route-1")

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token-for-test'})
    @patch('requests.get')
    def test_successful_routing_with_text_geocoding(self, mock_get):
        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.ok = True
            resp.status_code = 200
            if "geocoding" in url:
                if "Chicago" in url:
                    resp.json.return_value = mock_geocoding_feature(41.8781, -87.6298, "Chicago, IL")
                else:
                    resp.json.return_value = mock_geocoding_feature(32.7767, -96.7970, "Dallas, TX")
            elif "directions" in url:
                resp.json.return_value = {
                    "code": "Ok",
                    "routes": [mock_mapbox_route(1488000.0, 50400.0, "I-55 S")]
                }
            return resp

        mock_get.side_effect = side_effect

        payload = {
            "origin": "Chicago, IL",
            "destination": "Dallas, TX",
            "departure_datetime": "2026-10-30T08:00:00Z",
            "load_weight_lb": 35000.0,
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "planned")
        self.assertEqual(len(data["routes"]), 1)
        self.assertEqual(data["request_summary"]["origin"], "Chicago, IL")

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token-for-test'})
    @patch('requests.get')
    def test_provider_auth_error_returns_502(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        data = response.json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["code"], "provider_auth_error")
        self.assertNotIn("pk.mock-token-for-test", json.dumps(data))

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token-for-test'})
    @patch('requests.get')
    def test_provider_rate_limit_returns_429(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp

        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        data = response.json()
        self.assertEqual(data["code"], "rate_limit_exceeded")

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token-for-test'})
    @patch('requests.get')
    def test_provider_timeout_returns_504(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_504_GATEWAY_TIMEOUT)
        data = response.json()
        self.assertEqual(data["code"], "provider_timeout")

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token-for-test'})
    @patch('requests.get')
    def test_provider_network_error_returns_502(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Network down")

        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        data = response.json()
        self.assertEqual(data["code"], "provider_connection_error")

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token-for-test'})
    @patch('requests.get')
    def test_provider_no_route_returns_404(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"code": "NoRoute", "routes": []}
        mock_get.return_value = mock_resp

        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.json()
        self.assertEqual(data["code"], "no_route_found")

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token-for-test'})
    @patch('requests.get')
    def test_geocoding_failure_returns_400(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"features": []}
        mock_get.return_value = mock_resp

        payload = {
            "origin": "CompletelyFakeCity123456789999",
            "destination": "Dallas, TX",
            "departure_datetime": "2026-10-30T08:00:00Z",
            "load_weight_lb": 35000.0,
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertEqual(data["code"], "geocoding_failed")

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token-for-test'})
    @patch('requests.get')
    def test_cors_on_routes_endpoint(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": "Ok",
            "routes": [mock_mapbox_route()]
        }
        mock_get.return_value = mock_resp

        response = self.client.post(
            self.url,
            self.valid_payload,
            format='json',
            HTTP_ORIGIN="http://localhost:5173"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get("Access-Control-Allow-Origin"), "http://localhost:5173")


class RouteResponseContractTests(APITestCase):
    """
    Validates that the response serializers can accurately represent up to 3 routes
    with all required checkpoints, weather observations, and risk scores.
    """
    def test_full_route_response_schema_validation(self):
        mock_data = {
            "status": "planned",
            "message": "Routes generated successfully.",
            "request_summary": {
                "origin": "Chicago, IL",
                "destination": "Dallas, TX",
                "departure_datetime": "2026-10-30T08:00:00Z",
                "load_weight_lb": 40000.0,
            },
            "routes": [
                {
                    "route_id": "mapbox-route-1",
                    "display_name": "I-55 S to I-30 W (Recommended)",
                    "distance_km": 1488.5,
                    "distance_miles": 925.4,
                    "duration_seconds": 51600,
                    "duration_formatted": "14h 20m",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-87.6298, 41.8781], [-96.7970, 32.7767]]
                    },
                    "checkpoints": [
                        {
                            "sequence": 1,
                            "name": "Chicago Origin",
                            "latitude": 41.8781,
                            "longitude": -87.6298,
                            "estimated_arrival": "2026-10-30T08:00:00Z",
                            "distance_from_origin_km": 0.0,
                            "distance_from_origin_miles": 0.0,
                            "duration_from_origin_seconds": 0,
                            "weather": {
                                "temperature": 45.0,
                                "condition": "Overcast",
                                "wind_speed_mph": 12.5,
                                "wind_gust_mph": 18.0,
                                "precipitation_probability": 10.0,
                                "visibility_miles": 10.0,
                                "units": {
                                    "temperature": "°F",
                                    "wind_speed": "mph",
                                    "precipitation": "%",
                                    "visibility": "miles"
                                }
                            },
                            "risk_level": "low",
                            "risk_summary": "Favorable driving conditions."
                        },
                        {
                            "sequence": 2,
                            "name": "Dallas Destination",
                            "latitude": 32.7767,
                            "longitude": -96.7970,
                            "estimated_arrival": "2026-10-30T22:20:00Z",
                            "distance_from_origin_km": 1488.5,
                            "distance_from_origin_miles": 925.4,
                            "duration_from_origin_seconds": 51600,
                            "weather": None,
                            "risk_level": "unknown",
                            "risk_summary": None
                        }
                    ],
                    "weather_summary": {},
                    "risk_assessment": {
                        "overall_risk_level": "low",
                        "risk_score": 15.0,
                        "risk_factors": [],
                        "summary": "Favorable driving conditions."
                    },
                    "recommendation": {
                        "is_recommended": True,
                        "status": "recommended",
                        "explanation": "Best balance of transit time and road conditions."
                    }
                }
            ]
        }

        serializer = RoutePlanResponseSerializer(data=mock_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(len(serializer.validated_data["routes"]), 1)
        route = serializer.validated_data["routes"][0]
        self.assertEqual(route["route_id"], "mapbox-route-1")
        self.assertEqual(route["recommendation"]["status"], "recommended")
        self.assertEqual(len(route["checkpoints"]), 2)


# =========================================================================
# Step 5: Open-Meteo Weather Service Tests
# =========================================================================

class OpenMeteoWeatherServiceTests(APITestCase):
    """
    Automated unit tests for OpenMeteoWeatherService covering:
    - Unit conversions (mph, in/h, °F)
    - Timestamp matching against arrival times
    - Preserving missing values as null (never zero)
    - Horizon limits
    - Provider error, timeout, and rate limit handling
    - Coordinate deduplication
    """

    def setUp(self):
        self.service = OpenMeteoWeatherService()

    def test_unit_conversions_and_variables(self):
        """Verifies correct units, rounding, and WMO code conversion."""
        raw_forecast = mock_open_meteo_forecast(
            base_time="2026-10-30T00:00",
            num_hours=24,
            wind_speed=18.4,
            wind_gust=26.3,
            precip=0.35,
            snow=0.15,
            temp=34.2,
            weather_code=71,  # Slight snow fall
            precip_prob=60.0,
        )

        arrival_dt = datetime(2026, 10, 30, 8, 20, tzinfo=timezone.utc)
        obs = self.service.match_forecast_for_arrival(raw_forecast, arrival_dt)

        self.assertEqual(obs["data_availability"], "available")
        self.assertEqual(obs["wind_speed_mph"], 18.4)
        self.assertEqual(obs["wind_gust_mph"], 26.3)
        self.assertEqual(obs["temperature"], 34.2)
        self.assertEqual(obs["precipitation_in_per_hour"], 0.35)
        self.assertEqual(obs["snowfall_in_per_hour"], 0.15)
        self.assertEqual(obs["precipitation_rate_in_per_hour"], 0.35)
        self.assertEqual(obs["snowfall_rate_in_per_hour"], 0.15)
        self.assertEqual(obs["precipitation_accumulation_in"], 0.35)
        self.assertEqual(obs["snowfall_accumulation_in"], 0.15)
        self.assertEqual(obs["condition"], "Slight snow fall")
        self.assertEqual(obs["weather_code"], 71)
        self.assertEqual(obs["units"]["wind_speed"], "mph")
        self.assertEqual(obs["units"]["precipitation"], "in/h")
        self.assertEqual(obs["units"]["snowfall"], "in/h")
        self.assertEqual(obs["units"]["temperature"], "°F")

    def test_timestamp_matching_closest_hourly_slot(self):
        """Verifies checkpoint arrival matches the nearest hour in UTC."""
        raw_forecast = mock_open_meteo_forecast(base_time="2026-10-30T00:00", num_hours=24)

        # 08:20 -> closest is 08:00
        arrival_1 = datetime(2026, 10, 30, 8, 20, tzinfo=timezone.utc)
        obs_1 = self.service.match_forecast_for_arrival(raw_forecast, arrival_1)
        self.assertEqual(obs_1["forecast_timestamp"], "2026-10-30T08:00:00+00:00")

        # 08:45 -> closest is 09:00
        arrival_2 = datetime(2026, 10, 30, 8, 45, tzinfo=timezone.utc)
        obs_2 = self.service.match_forecast_for_arrival(raw_forecast, arrival_2)
        self.assertEqual(obs_2["forecast_timestamp"], "2026-10-30T09:00:00+00:00")

    def test_missing_weather_values_preserved_as_null_not_zero(self):
        """Missing provider values must remain None, never defaulted to 0.0."""
        raw_forecast = mock_open_meteo_forecast(base_time="2026-10-30T00:00", num_hours=12)
        # Set precipitation, snowfall, and wind speed to None for slot 5 (05:00)
        raw_forecast["hourly"]["precipitation"][5] = None
        raw_forecast["hourly"]["snowfall"][5] = None
        raw_forecast["hourly"]["wind_speed_10m"][5] = None

        arrival_dt = datetime(2026, 10, 30, 5, 0, tzinfo=timezone.utc)
        obs = self.service.match_forecast_for_arrival(raw_forecast, arrival_dt)

        self.assertIsNone(obs["precipitation_in_per_hour"])
        self.assertIsNone(obs["snowfall_in_per_hour"])
        self.assertIsNone(obs["wind_speed_mph"])
        self.assertEqual(obs["data_availability"], "partial")
        # Ensure limitations explicitly mention missing values
        limitations_joined = " ".join(obs["limitations"])
        self.assertIn("represented as null rather than treated as zero", limitations_joined)

    def test_checkpoint_arrival_out_of_forecast_horizon(self):
        """Arrival dates beyond provider forecast horizon return out_of_forecast_horizon and nulls."""
        raw_forecast = mock_open_meteo_forecast(base_time="2026-10-30T00:00", num_hours=48)
        # 30 days later
        far_future_arrival = datetime(2026, 11, 30, 12, 0, tzinfo=timezone.utc)
        obs = self.service.match_forecast_for_arrival(raw_forecast, far_future_arrival)

        self.assertEqual(obs["data_availability"], "out_of_forecast_horizon")
        self.assertIsNone(obs["temperature"])
        self.assertIsNone(obs["wind_speed_mph"])
        self.assertIsNone(obs["precipitation_in_per_hour"])
        self.assertIsNone(obs["snowfall_in_per_hour"])
        self.assertIn("outside the available Open-Meteo forecast horizon", obs["notes"])

    @patch('requests.get')
    def test_provider_timeout_marks_checkpoints_unavailable(self, mock_get):
        """API timeout must safely mark checkpoints as unavailable without crashing."""
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        checkpoints = [
            {
                "sequence": 1,
                "latitude": 41.8781,
                "longitude": -87.6298,
                "estimated_arrival": "2026-10-30T08:00:00Z",
                "weather": None,
            }
        ]

        result = self.service.get_weather_for_checkpoints(checkpoints)
        self.assertEqual(len(result), 1)
        weather = result[0]["weather"]
        self.assertEqual(weather["data_availability"], "unavailable")
        self.assertIn("timed out", weather["notes"])
        self.assertIsNone(weather["wind_speed_mph"])

    @patch('requests.get')
    def test_provider_connection_error_handled_safely(self, mock_get):
        """Network error must safely mark checkpoints as unavailable."""
        mock_get.side_effect = requests.exceptions.ConnectionError("DNS failure")

        checkpoints = [
            {
                "sequence": 1,
                "latitude": 41.8781,
                "longitude": -87.6298,
                "estimated_arrival": "2026-10-30T08:00:00Z",
                "weather": None,
            }
        ]

        result = self.service.get_weather_for_checkpoints(checkpoints)
        weather = result[0]["weather"]
        self.assertEqual(weather["data_availability"], "unavailable")
        self.assertIn("Unable to connect", weather["notes"])

    @patch('requests.get')
    def test_provider_rate_limit_handled_safely(self, mock_get):
        """HTTP 429 from provider marks checkpoints as unavailable."""
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 429
        mock_get.return_value = mock_resp

        checkpoints = [
            {
                "sequence": 1,
                "latitude": 41.8781,
                "longitude": -87.6298,
                "estimated_arrival": "2026-10-30T08:00:00Z",
                "weather": None,
            }
        ]

        result = self.service.get_weather_for_checkpoints(checkpoints)
        weather = result[0]["weather"]
        self.assertEqual(weather["data_availability"], "unavailable")
        self.assertIn("rate limit", weather["notes"])

    @patch('requests.get')
    def test_provider_malformed_response_handled_safely(self, mock_get):
        """Malformed response missing hourly block marks checkpoints as unavailable."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"error": False, "some_other_field": 123}
        mock_get.return_value = mock_resp

        checkpoints = [
            {
                "sequence": 1,
                "latitude": 41.8781,
                "longitude": -87.6298,
                "estimated_arrival": "2026-10-30T08:00:00Z",
                "weather": None,
            }
        ]

        result = self.service.get_weather_for_checkpoints(checkpoints)
        weather = result[0]["weather"]
        self.assertEqual(weather["data_availability"], "unavailable")
        self.assertIn("missing required 'hourly' block", weather["notes"])

    @patch('requests.get')
    def test_coordinate_deduplication_avoids_repeated_calls(self, mock_get):
        """Multiple checkpoints with identical coordinates query provider only once."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_open_meteo_forecast()
        mock_get.return_value = mock_resp

        checkpoints = [
            {
                "sequence": 1,
                "latitude": 41.8781,
                "longitude": -87.6298,
                "estimated_arrival": "2026-10-30T08:00:00Z",
                "weather": None,
            },
            {
                "sequence": 2,
                "latitude": 41.8781,
                "longitude": -87.6298,
                "estimated_arrival": "2026-10-30T09:00:00Z",
                "weather": None,
            },
            {
                "sequence": 3,
                "latitude": 41.8782,  # rounds to same 3 decimal places (41.878)
                "longitude": -87.6298,
                "estimated_arrival": "2026-10-30T10:00:00Z",
                "weather": None,
            },
        ]

        self.service.get_weather_for_checkpoints(checkpoints)
        self.assertEqual(mock_get.call_count, 1)
        call_params = mock_get.call_args[1]["params"]
        # Only 1 unique latitude in comma-separated string
        latitudes = call_params["latitude"].split(",")
        self.assertEqual(len(latitudes), 1)

    @patch('requests.get')
    def test_attach_weather_to_routes_summary_calculation(self, mock_get):
        """attach_weather_to_routes updates checkpoints and computes summary maxima."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_open_meteo_forecast(
            wind_speed=24.5,
            precip=0.45,
            snow=0.20,
            weather_code=65,  # Heavy rain
        )
        mock_get.return_value = mock_resp

        routes = [
            {
                "route_id": "route-1",
                "checkpoints": [
                    {
                        "sequence": 1,
                        "latitude": 41.8781,
                        "longitude": -87.6298,
                        "estimated_arrival": "2026-10-30T08:00:00Z",
                        "weather": None,
                    },
                    {
                        "sequence": 2,
                        "latitude": 38.6270,
                        "longitude": -90.1994,
                        "estimated_arrival": "2026-10-30T12:00:00Z",
                        "weather": None,
                    },
                ],
                "weather_summary": {},
            }
        ]

        self.service.attach_weather_to_routes(routes)
        summary = routes[0]["weather_summary"]

        self.assertEqual(summary["total_checkpoints"], 2)
        self.assertEqual(summary["available_checkpoints"], 2)
        self.assertEqual(summary["max_wind_speed_mph"], 24.5)
        self.assertEqual(summary["max_precipitation_in_per_hour"], 0.45)
        self.assertEqual(summary["max_snowfall_in_per_hour"], 0.20)
        self.assertIn("Heavy rain", summary["conditions_observed"])
        self.assertIn("Open-Meteo Forecast API", summary["provider"])


# =========================================================================
# Step 5: Checkpoint Sampling Tests (10, 25, 50 miles)
# =========================================================================

class CheckpointSamplingTests(APITestCase):
    """
    Tests checkpoint sampling at 10, 25, and 50 miles intervals.
    Verifies miles-to-km conversion, sequence ordering, endpoint preservation,
    and invalid interval rejection.
    """

    def setUp(self):
        self.routing_service = MapboxRoutingService(token="pk.mock-token")
        self.route_distance_m = 1488000.0  # 924.9 miles
        self.route_duration_s = 50400  # 14 hours
        self.departure_dt = datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc)

    @patch('requests.get')
    def test_checkpoint_sampling_at_10_miles(self, mock_get):
        """Sampling at 10-mile intervals generates checkpoints every ~10 miles."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": "Ok",
            "routes": [mock_mapbox_route(self.route_distance_m, self.route_duration_s)]
        }
        mock_get.return_value = mock_resp

        routes = self.routing_service.calculate_routes(
            origin={"latitude": 41.8781, "longitude": -87.6298},
            destination={"latitude": 32.7767, "longitude": -96.7970},
            departure_datetime=self.departure_dt,
            load_weight_lb=35000.0,
            checkpoint_interval_miles=10,
        )

        checkpoints = routes[0]["checkpoints"]
        # Expected marks: 10, 20, 30 ... up to 920 miles, plus origin (0) and destination (924.9)
        self.assertGreaterEqual(len(checkpoints), 90)

        # Sequence ordering 1, 2, 3...
        for idx, cp in enumerate(checkpoints, start=1):
            self.assertEqual(cp["sequence"], idx)

        # First is departure at 0.0 mi and 0.0 km
        self.assertEqual(checkpoints[0]["distance_from_origin_miles"], 0.0)
        self.assertEqual(checkpoints[0]["distance_from_origin_km"], 0.0)
        self.assertIn("Departure", checkpoints[0]["name"])

        # Second is at 10.0 mi and 16.1 km (10 * 1.609344 = 16.09 -> 16.1)
        self.assertEqual(checkpoints[1]["distance_from_origin_miles"], 10.0)
        self.assertEqual(checkpoints[1]["distance_from_origin_km"], 16.1)

        # Third is at 20.0 mi and 32.2 km
        self.assertEqual(checkpoints[2]["distance_from_origin_miles"], 20.0)
        self.assertEqual(checkpoints[2]["distance_from_origin_km"], 32.2)

        # Last is arrival
        self.assertEqual(checkpoints[-1]["distance_from_origin_miles"], 924.6)
        self.assertIn("Arrival", checkpoints[-1]["name"])

    @patch('requests.get')
    def test_checkpoint_sampling_at_25_miles(self, mock_get):
        """Sampling at 25-mile intervals generates checkpoints every 25 miles."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": "Ok",
            "routes": [mock_mapbox_route(self.route_distance_m, self.route_duration_s)]
        }
        mock_get.return_value = mock_resp

        routes = self.routing_service.calculate_routes(
            origin={"latitude": 41.8781, "longitude": -87.6298},
            destination={"latitude": 32.7767, "longitude": -96.7970},
            departure_datetime=self.departure_dt,
            load_weight_lb=35000.0,
            checkpoint_interval_miles=25,
        )

        checkpoints = routes[0]["checkpoints"]
        # Marks: 25, 50, 75 ... 900 miles (36 intermediate + 2 endpoints = 38 checkpoints)
        self.assertEqual(len(checkpoints), 38)
        self.assertEqual(checkpoints[1]["distance_from_origin_miles"], 25.0)
        self.assertEqual(checkpoints[1]["distance_from_origin_km"], 40.2)  # 25 * 1.609344 = 40.23 -> 40.2
        self.assertEqual(checkpoints[2]["distance_from_origin_miles"], 50.0)
        self.assertEqual(checkpoints[2]["distance_from_origin_km"], 80.5)  # 50 * 1.609344 = 80.47 -> 80.5

    @patch('requests.get')
    def test_checkpoint_sampling_at_50_miles(self, mock_get):
        """Sampling at 50-mile intervals generates checkpoints every 50 miles."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "code": "Ok",
            "routes": [mock_mapbox_route(self.route_distance_m, self.route_duration_s)]
        }
        mock_get.return_value = mock_resp

        routes = self.routing_service.calculate_routes(
            origin={"latitude": 41.8781, "longitude": -87.6298},
            destination={"latitude": 32.7767, "longitude": -96.7970},
            departure_datetime=self.departure_dt,
            load_weight_lb=35000.0,
            checkpoint_interval_miles=50,
        )

        checkpoints = routes[0]["checkpoints"]
        # Marks: 50, 100 ... 900 miles (18 intermediate + 2 endpoints = 20 checkpoints)
        self.assertEqual(len(checkpoints), 20)
        self.assertEqual(checkpoints[1]["distance_from_origin_miles"], 50.0)
        self.assertEqual(checkpoints[1]["distance_from_origin_km"], 80.5)
        self.assertEqual(checkpoints[2]["distance_from_origin_miles"], 100.0)
        self.assertEqual(checkpoints[2]["distance_from_origin_km"], 160.9)

    def test_invalid_checkpoint_interval_rejected_by_serializer(self):
        """Unsupported intervals (e.g. 15, 100) must fail validation with 400 Bad Request."""
        payload_15 = {
            "origin": "Chicago, IL",
            "destination": "Dallas, TX",
            "departure_datetime": "2026-10-30T08:00:00Z",
            "load_weight_lb": 35000.0,
            "checkpoint_interval_miles": 15,
        }
        s15 = RoutePlanRequestSerializer(data=payload_15)
        self.assertFalse(s15.is_valid())
        self.assertIn("checkpoint_interval_miles", s15.errors)

        payload_100 = {
            "origin": "Chicago, IL",
            "destination": "Dallas, TX",
            "departure_datetime": "2026-10-30T08:00:00Z",
            "load_weight_lb": 35000.0,
            "checkpoint_interval_miles": 100,
        }
        s100 = RoutePlanRequestSerializer(data=payload_100)
        self.assertFalse(s100.is_valid())
        self.assertIn("checkpoint_interval_miles", s100.errors)

    @patch('requests.get')
    def test_short_route_sampling_preserves_start_and_end_no_duplicates(self, mock_get):
        """Routes shorter than the interval produce exactly Departure and Arrival without duplicates."""
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        # 5 miles (8046.7 meters)
        mock_resp.json.return_value = {
            "code": "Ok",
            "routes": [mock_mapbox_route(8046.7, 600.0, "Short Street")]
        }
        mock_get.return_value = mock_resp

        routes = self.routing_service.calculate_routes(
            origin={"latitude": 41.8781, "longitude": -87.6298},
            destination={"latitude": 41.9000, "longitude": -87.6500},
            departure_datetime=self.departure_dt,
            load_weight_lb=35000.0,
            checkpoint_interval_miles=25,
        )

        checkpoints = routes[0]["checkpoints"]
        self.assertEqual(len(checkpoints), 2)
        self.assertEqual(checkpoints[0]["sequence"], 1)
        self.assertEqual(checkpoints[0]["distance_from_origin_miles"], 0.0)
        self.assertEqual(checkpoints[1]["sequence"], 2)
        self.assertEqual(checkpoints[1]["distance_from_origin_miles"], 5.0)


# =========================================================================
# Step 5: Route Planning API End-to-End Weather Integration Tests
# =========================================================================

class RoutePlanningWeatherIntegrationTests(APITestCase):
    """
    End-to-end integration tests for POST /api/routes/ with mocked Mapbox and Open-Meteo providers.
    """

    def setUp(self):
        self.url = reverse('plan_routes')
        self.valid_payload = {
            "origin": "Chicago, IL",
            "destination": "Dallas, TX",
            "departure_datetime": "2026-10-30T08:00:00Z",
            "load_weight_lb": 35000.0,
            "checkpoint_interval_miles": 50,
        }

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token'})
    @patch('requests.get')
    def test_route_planning_with_weather_forecasts_end_to_end(self, mock_get):
        """Verifies end-to-end planning with checkpoints annotated with Open-Meteo forecasts."""
        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.ok = True
            resp.status_code = 200
            if "mapbox.places" in url:
                resp.json.return_value = mock_geocoding_feature()
            elif "mapbox/driving" in url:
                resp.json.return_value = {
                    "code": "Ok",
                    "routes": [mock_mapbox_route(1488000.0, 50400.0)]
                }
            elif "open-meteo" in url:
                resp.json.return_value = mock_open_meteo_forecast(
                    wind_speed=14.0,
                    precip=0.10,
                    snow=0.0,
                    temp=42.0,
                    weather_code=3,  # Overcast
                )
            else:
                resp.json.return_value = {}
            return resp

        mock_get.side_effect = side_effect

        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["status"], "planned")
        self.assertEqual(data["request_summary"]["checkpoint_interval_miles"], 50)
        self.assertEqual(len(data["routes"]), 1)

        primary = data["routes"][0]
        checkpoints = primary["checkpoints"]
        self.assertGreater(len(checkpoints), 2)

        # First checkpoint weather check
        cp0 = checkpoints[0]
        self.assertIsNotNone(cp0["weather"])
        w0 = cp0["weather"]
        self.assertEqual(w0["data_availability"], "available")
        self.assertEqual(w0["wind_speed_mph"], 14.0)
        self.assertEqual(w0["precipitation_in_per_hour"], 0.10)
        self.assertEqual(w0["snowfall_in_per_hour"], 0.0)
        self.assertEqual(w0["temperature"], 42.0)
        self.assertEqual(w0["condition"], "Overcast")
        self.assertEqual(w0["units"]["wind_speed"], "mph")
        self.assertEqual(w0["units"]["precipitation"], "in/h")
        self.assertEqual(w0["units"]["snowfall"], "in/h")

        # Weather summary check
        summary = primary["weather_summary"]
        self.assertEqual(summary["provider"], "Open-Meteo Forecast API")
        self.assertEqual(summary["available_checkpoints"], len(checkpoints))
        self.assertEqual(summary["max_wind_speed_mph"], 14.0)
        self.assertIn("Overcast", summary["conditions_observed"])

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token'})
    @patch('requests.get')
    def test_route_planning_resilient_when_weather_provider_times_out(self, mock_get):
        """When weather provider times out, route planning still succeeds with unavailable weather status."""
        def side_effect(url, **kwargs):
            if "mapbox.places" in url:
                resp = MagicMock()
                resp.ok = True
                resp.status_code = 200
                resp.json.return_value = mock_geocoding_feature()
                return resp
            elif "mapbox/driving" in url:
                resp = MagicMock()
                resp.ok = True
                resp.status_code = 200
                resp.json.return_value = {
                    "code": "Ok",
                    "routes": [mock_mapbox_route(1488000.0, 50400.0)]
                }
                return resp
            elif "open-meteo" in url:
                raise requests.exceptions.Timeout("Weather service timeout")
            return MagicMock()

        mock_get.side_effect = side_effect

        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        primary = data["routes"][0]
        self.assertGreater(len(primary["checkpoints"]), 0)
        cp_weather = primary["checkpoints"][0]["weather"]
        self.assertEqual(cp_weather["data_availability"], "unavailable")
        self.assertIn("timed out", cp_weather["notes"])


# =========================================================================
# Step 6: Weather Risk Scoring Engine Unit & Integration Tests
# =========================================================================

class WeatherRiskServiceThresholdTests(APITestCase):
    """
    Automated unit tests for WeatherRiskService verifying:
    - Exact wind threshold boundaries
    - Load-specific wind elevation rules (55+ mph, 45-54 mph > 30k, 35-44 mph > 40k)
    - Exact precipitation threshold boundaries
    - Exact snowfall threshold boundaries
    - Multiple simultaneous hazards (most severe applied, components preserved)
    - Explicit handling of missing weather data (never defaulted to zero, never assumed Low)
    """

    def setUp(self):
        self.service = WeatherRiskService()

    # --- Wind Thresholds & Load Rules ---

    def test_wind_threshold_low(self):
        """Wind below 25 mph evaluates to Low across all loads."""
        for speed in [0.0, 10.0, 24.0, 24.9]:
            res = self.service.evaluate_wind_risk(speed, load_weight_lb=50000.0)
            self.assertEqual(res["risk_level"], RISK_LEVEL_LOW)
            self.assertEqual(res["score"], 10.0)
            self.assertFalse(res["is_elevated_by_load"])

    def test_wind_threshold_moderate(self):
        """Wind 25–34 mph evaluates to Moderate across all loads."""
        for speed in [25.0, 29.5, 34.0, 34.9]:
            res = self.service.evaluate_wind_risk(speed, load_weight_lb=50000.0)
            self.assertEqual(res["risk_level"], RISK_LEVEL_MODERATE)
            self.assertEqual(res["score"], 35.0)
            self.assertFalse(res["is_elevated_by_load"])

    def test_wind_threshold_high_unmodified_by_light_load(self):
        """Wind 35–44 mph with load <= 40,000 lb evaluates to High."""
        for speed in [35.0, 40.0, 44.0, 44.9]:
            res = self.service.evaluate_wind_risk(speed, load_weight_lb=25000.0)
            self.assertEqual(res["risk_level"], RISK_LEVEL_HIGH)
            self.assertEqual(res["score"], 60.0)
            self.assertFalse(res["is_elevated_by_load"])

        # Boundary: exactly 40,000 lb is not above 40,000 lb
        res_boundary = self.service.evaluate_wind_risk(38.0, load_weight_lb=40000.0)
        self.assertEqual(res_boundary["risk_level"], RISK_LEVEL_HIGH)
        self.assertFalse(res_boundary["is_elevated_by_load"])

    def test_wind_load_rule_35_to_45_elevates_to_severe_above_40k(self):
        """Wind 35 to <45 mph elevates to Severe when load weight > 40,000 lb."""
        # 40,001 lb is above 40,000 lb
        res_40001 = self.service.evaluate_wind_risk(35.0, load_weight_lb=40001.0)
        self.assertEqual(res_40001["risk_level"], RISK_LEVEL_SEVERE)
        self.assertEqual(res_40001["score"], 80.0)
        self.assertTrue(res_40001["is_elevated_by_load"])

        res_heavy = self.service.evaluate_wind_risk(42.0, load_weight_lb=50000.0)
        self.assertEqual(res_heavy["risk_level"], RISK_LEVEL_SEVERE)
        self.assertTrue(res_heavy["is_elevated_by_load"])

    def test_wind_threshold_severe_unmodified_by_light_load(self):
        """Wind 45–54 mph with load <= 30,000 lb evaluates to Severe."""
        for speed in [45.0, 50.0, 54.0, 54.9]:
            res = self.service.evaluate_wind_risk(speed, load_weight_lb=25000.0)
            self.assertEqual(res["risk_level"], RISK_LEVEL_SEVERE)
            self.assertEqual(res["score"], 80.0)
            self.assertFalse(res["is_elevated_by_load"])

        # Boundary: exactly 30,000 lb is not above 30,000 lb
        res_boundary = self.service.evaluate_wind_risk(48.0, load_weight_lb=30000.0)
        self.assertEqual(res_boundary["risk_level"], RISK_LEVEL_SEVERE)
        self.assertFalse(res_boundary["is_elevated_by_load"])

    def test_wind_load_rule_45_to_55_elevates_to_no_travel_above_30k(self):
        """Wind 45 to <55 mph elevates to No Travel when load weight > 30,000 lb."""
        # 30,001 lb is above 30,000 lb
        res_30001 = self.service.evaluate_wind_risk(45.0, load_weight_lb=30001.0)
        self.assertEqual(res_30001["risk_level"], RISK_LEVEL_NO_TRAVEL)
        self.assertEqual(res_30001["score"], 100.0)
        self.assertTrue(res_30001["is_elevated_by_load"])

        res_heavy = self.service.evaluate_wind_risk(50.0, load_weight_lb=45000.0)
        self.assertEqual(res_heavy["risk_level"], RISK_LEVEL_NO_TRAVEL)
        self.assertTrue(res_heavy["is_elevated_by_load"])

    def test_wind_rule_55_plus_no_travel_for_every_load(self):
        """Wind at or above 55 mph means No Travel for every load."""
        for speed in [55.0, 60.0, 80.0]:
            for load in [5000.0, 20000.0, 30000.0, 45000.0, 80000.0]:
                res = self.service.evaluate_wind_risk(speed, load_weight_lb=load)
                self.assertEqual(res["risk_level"], RISK_LEVEL_NO_TRAVEL)
                self.assertEqual(res["score"], 100.0)

    # --- Precipitation Thresholds ---

    def test_precipitation_thresholds(self):
        """Verifies liquid precipitation rate thresholds (in/h)."""
        # Low: below 0.10
        for rate in [0.0, 0.05, 0.09]:
            res = self.service.evaluate_precipitation_risk(rate)
            self.assertEqual(res["risk_level"], RISK_LEVEL_LOW)
            self.assertEqual(res["score"], 10.0)

        # Moderate: 0.10–0.25
        for rate in [0.10, 0.18, 0.25]:
            res = self.service.evaluate_precipitation_risk(rate)
            self.assertEqual(res["risk_level"], RISK_LEVEL_MODERATE)
            self.assertEqual(res["score"], 35.0)

        # High: above 0.25–0.50
        for rate in [0.26, 0.40, 0.50]:
            res = self.service.evaluate_precipitation_risk(rate)
            self.assertEqual(res["risk_level"], RISK_LEVEL_HIGH)
            self.assertEqual(res["score"], 60.0)

        # Severe: above 0.50–1.00
        for rate in [0.51, 0.75, 1.00]:
            res = self.service.evaluate_precipitation_risk(rate)
            self.assertEqual(res["risk_level"], RISK_LEVEL_SEVERE)
            self.assertEqual(res["score"], 80.0)

        # No Travel: above 1.00
        for rate in [1.01, 1.50, 3.00]:
            res = self.service.evaluate_precipitation_risk(rate)
            self.assertEqual(res["risk_level"], RISK_LEVEL_NO_TRAVEL)
            self.assertEqual(res["score"], 100.0)

    # --- Snowfall Thresholds ---

    def test_snowfall_thresholds(self):
        """Verifies snowfall rate thresholds (in/h)."""
        # Low: below 0.5
        for rate in [0.0, 0.2, 0.49]:
            res = self.service.evaluate_snowfall_risk(rate)
            self.assertEqual(res["risk_level"], RISK_LEVEL_LOW)
            self.assertEqual(res["score"], 10.0)

        # Moderate: 0.5–1.0
        for rate in [0.50, 0.80, 1.00]:
            res = self.service.evaluate_snowfall_risk(rate)
            self.assertEqual(res["risk_level"], RISK_LEVEL_MODERATE)
            self.assertEqual(res["score"], 35.0)

        # High: above 1.0–2.0
        for rate in [1.01, 1.50, 2.00]:
            res = self.service.evaluate_snowfall_risk(rate)
            self.assertEqual(res["risk_level"], RISK_LEVEL_HIGH)
            self.assertEqual(res["score"], 60.0)

        # Severe: above 2.0–3.0
        for rate in [2.01, 2.50, 3.00]:
            res = self.service.evaluate_snowfall_risk(rate)
            self.assertEqual(res["risk_level"], RISK_LEVEL_SEVERE)
            self.assertEqual(res["score"], 80.0)

        # No Travel: above 3.0
        for rate in [3.01, 3.50, 5.00]:
            res = self.service.evaluate_snowfall_risk(rate)
            self.assertEqual(res["risk_level"], RISK_LEVEL_NO_TRAVEL)
            self.assertEqual(res["score"], 100.0)

    # --- Simultaneous Hazards & Checkpoint Evaluation ---

    def test_simultaneous_hazards_highest_severity_governs_checkpoint(self):
        """When multiple hazards are active, the most severe governs overall checkpoint risk."""
        # Case A: Wind Moderate (28 mph), Precip Severe (0.65 in/h), Snow Low (0.0)
        cp_a = {
            "sequence": 1,
            "latitude": 41.8781,
            "longitude": -87.6298,
            "weather": {
                "wind_speed_mph": 28.0,
                "precipitation_in_per_hour": 0.65,
                "snowfall_in_per_hour": 0.0,
                "data_availability": "available",
            }
        }
        res_a = self.service.evaluate_checkpoint_risk(cp_a, load_weight_lb=35000.0)
        self.assertEqual(res_a["risk_level"], RISK_LEVEL_SEVERE)
        self.assertEqual(res_a["risk_score"], 80.0)
        self.assertEqual(res_a["risk_components"]["wind"]["risk_level"], RISK_LEVEL_MODERATE)
        self.assertEqual(res_a["risk_components"]["precipitation"]["risk_level"], RISK_LEVEL_SEVERE)
        self.assertEqual(res_a["risk_components"]["snowfall"]["risk_level"], RISK_LEVEL_LOW)

        # Case B: Wind High (40 mph, load 25k -> High), Precip Low, Snow No Travel (3.5 in/h)
        cp_b = {
            "sequence": 2,
            "latitude": 41.8781,
            "longitude": -87.6298,
            "weather": {
                "wind_speed_mph": 40.0,
                "precipitation_in_per_hour": 0.05,
                "snowfall_in_per_hour": 3.5,
                "data_availability": "available",
            }
        }
        res_b = self.service.evaluate_checkpoint_risk(cp_b, load_weight_lb=25000.0)
        self.assertEqual(res_b["risk_level"], RISK_LEVEL_NO_TRAVEL)
        self.assertEqual(res_b["risk_score"], 100.0)
        self.assertEqual(res_b["risk_components"]["snowfall"]["risk_level"], RISK_LEVEL_NO_TRAVEL)

        # Case C: Wind 38 mph elevated to Severe by load > 40k, Precip Moderate (0.20 in/h)
        cp_c = {
            "sequence": 3,
            "latitude": 41.8781,
            "longitude": -87.6298,
            "weather": {
                "wind_speed_mph": 38.0,
                "precipitation_in_per_hour": 0.20,
                "snowfall_in_per_hour": 0.0,
                "data_availability": "available",
            }
        }
        res_c = self.service.evaluate_checkpoint_risk(cp_c, load_weight_lb=45000.0)
        self.assertEqual(res_c["risk_level"], RISK_LEVEL_SEVERE)
        self.assertTrue(res_c["risk_components"]["wind"]["is_elevated_by_load"])

    # --- Missing Weather Data Handling ---

    def test_missing_weather_data_handling(self):
        """Missing values are never defaulted to zero and never assigned Low risk."""
        # 1. Weather completely missing or marked unavailable
        cp_none = {
            "sequence": 1,
            "latitude": 41.8781,
            "longitude": -87.6298,
            "weather": None,
        }
        res_none = self.service.evaluate_checkpoint_risk(cp_none, load_weight_lb=35000.0)
        self.assertEqual(res_none["risk_level"], RISK_LEVEL_UNKNOWN)
        self.assertIsNone(res_none["risk_score"])
        self.assertEqual(res_none["data_quality"], "unavailable")

        # 2. Known measurements are Low, but others are missing
        # Requirement 8: Do not assign Low risk when data is unknown!
        cp_partial_low = {
            "sequence": 2,
            "latitude": 41.8781,
            "longitude": -87.6298,
            "weather": {
                "wind_speed_mph": 12.0,  # Low
                "precipitation_in_per_hour": None,  # Missing
                "snowfall_in_per_hour": None,  # Missing
                "data_availability": "partial",
            }
        }
        res_partial_low = self.service.evaluate_checkpoint_risk(cp_partial_low, load_weight_lb=35000.0)
        self.assertEqual(res_partial_low["risk_level"], RISK_LEVEL_UNKNOWN)
        self.assertIsNone(res_partial_low["risk_score"])
        self.assertEqual(res_partial_low["data_quality"], "partial")

        # 3. Known measurement is No Travel, others missing
        # Since wind alone warrants No Travel, No Travel holds with partial data quality
        cp_partial_notravel = {
            "sequence": 3,
            "latitude": 41.8781,
            "longitude": -87.6298,
            "weather": {
                "wind_speed_mph": 58.0,  # No Travel
                "precipitation_in_per_hour": None,
                "snowfall_in_per_hour": None,
                "data_availability": "partial",
            }
        }
        res_partial_notravel = self.service.evaluate_checkpoint_risk(cp_partial_notravel, load_weight_lb=35000.0)
        self.assertEqual(res_partial_notravel["risk_level"], RISK_LEVEL_NO_TRAVEL)
        self.assertEqual(res_partial_notravel["score"] if "score" in res_partial_notravel else res_partial_notravel["risk_score"], 100.0)
        self.assertEqual(res_partial_notravel["data_quality"], "partial")


class WeatherRiskServiceRouteSummaryTests(APITestCase):
    """
    Automated unit tests for route-level risk aggregation, segment distance attribution,
    mileage categorization, and weighted average risk scores.
    """

    def setUp(self):
        self.service = WeatherRiskService()

    def test_segment_distance_attribution_and_category_mileage(self):
        """Verifies segment distance attribution sums precisely to total route distance."""
        # 5 checkpoints at 0, 25, 50, 75, 100 miles
        # Total distance = 100.0 miles
        checkpoints = [
            {
                "sequence": 1,
                "distance_from_origin_miles": 0.0,
                "weather": {"wind_speed_mph": 10.0, "precipitation_in_per_hour": 0.0, "snowfall_in_per_hour": 0.0, "data_availability": "available"},
            },
            {
                "sequence": 2,
                "distance_from_origin_miles": 25.0,
                "weather": {"wind_speed_mph": 28.0, "precipitation_in_per_hour": 0.0, "snowfall_in_per_hour": 0.0, "data_availability": "available"},
            },
            {
                "sequence": 3,
                "distance_from_origin_miles": 50.0,
                "weather": {"wind_speed_mph": 38.0, "precipitation_in_per_hour": 0.0, "snowfall_in_per_hour": 0.0, "data_availability": "available"},
            },
            {
                "sequence": 4,
                "distance_from_origin_miles": 75.0,
                "weather": {"wind_speed_mph": 48.0, "precipitation_in_per_hour": 0.0, "snowfall_in_per_hour": 0.0, "data_availability": "available"},
            },
            {
                "sequence": 5,
                "distance_from_origin_miles": 100.0,
                "weather": {"wind_speed_mph": 60.0, "precipitation_in_per_hour": 0.0, "snowfall_in_per_hour": 0.0, "data_availability": "available"},
            },
        ]

        route_data = {
            "distance_miles": 100.0,
            "checkpoints": checkpoints,
        }

        # Load weight 25,000 lb:
        # cp1 (0 mi): Low (length: 12.5 mi)
        # cp2 (25 mi): Moderate (length: 25.0 mi)
        # cp3 (50 mi): High (length: 25.0 mi)
        # cp4 (75 mi): Severe (length: 25.0 mi)
        # cp5 (100 mi): No Travel (length: 12.5 mi)
        assessment = self.service.evaluate_route_risk(route_data, load_weight_lb=25000.0)

        self.assertEqual(assessment["total_distance_miles"], 100.0)
        self.assertEqual(assessment["low_risk_miles"], 12.5)
        self.assertEqual(assessment["moderate_risk_miles"], 25.0)
        self.assertEqual(assessment["high_risk_miles"], 25.0)
        self.assertEqual(assessment["severe_risk_miles"], 25.0)
        self.assertEqual(assessment["no_travel_miles"], 12.5)

        # Sum of category miles equals total distance
        total_sum = (
            assessment["low_risk_miles"]
            + assessment["moderate_risk_miles"]
            + assessment["high_risk_miles"]
            + assessment["severe_risk_miles"]
            + assessment["no_travel_miles"]
        )
        self.assertAlmostEqual(total_sum, 100.0, places=1)

        # Overall level is No Travel due to cp5
        self.assertEqual(assessment["overall_risk_level"], RISK_LEVEL_NO_TRAVEL)
        self.assertEqual(assessment["no_travel_segments_count"], 1)
        self.assertTrue(assessment["no_travel_warning"])
        self.assertIn("NO TRAVEL WARNING", assessment["summary"])

        # Weighted score: (12.5*10 + 25*35 + 25*60 + 25*80 + 12.5*100) / 100 = (125 + 875 + 1500 + 2000 + 1250) / 100 = 5750 / 100 = 57.5
        self.assertEqual(assessment["risk_score"], 57.5)

        # Assumptions documented
        self.assertGreaterEqual(len(assessment["assumptions"]), 4)

    def test_route_summary_all_low_risk(self):
        """A route with all favorable weather evaluates to Low overall."""
        checkpoints = [
            {
                "sequence": 1,
                "distance_from_origin_miles": 0.0,
                "weather": {"wind_speed_mph": 10.0, "precipitation_in_per_hour": 0.0, "snowfall_in_per_hour": 0.0, "data_availability": "available"},
            },
            {
                "sequence": 2,
                "distance_from_origin_miles": 50.0,
                "weather": {"wind_speed_mph": 12.0, "precipitation_in_per_hour": 0.02, "snowfall_in_per_hour": 0.0, "data_availability": "available"},
            },
        ]
        route_data = {"distance_miles": 50.0, "checkpoints": checkpoints}
        assessment = self.service.evaluate_route_risk(route_data, load_weight_lb=35000.0)

        self.assertEqual(assessment["overall_risk_level"], RISK_LEVEL_LOW)
        self.assertEqual(assessment["low_risk_miles"], 50.0)
        self.assertEqual(assessment["no_travel_segments_count"], 0)
        self.assertFalse(assessment["no_travel_warning"])
        self.assertEqual(assessment["risk_score"], 10.0)
        self.assertIn("LOW RISK", assessment["summary"])

    def test_route_summary_all_unknown_weather(self):
        """A route with completely unknown weather evaluates to Unknown with null score."""
        checkpoints = [
            {"sequence": 1, "distance_from_origin_miles": 0.0, "weather": None},
            {"sequence": 2, "distance_from_origin_miles": 40.0, "weather": None},
        ]
        route_data = {"distance_miles": 40.0, "checkpoints": checkpoints}
        assessment = self.service.evaluate_route_risk(route_data, load_weight_lb=35000.0)

        self.assertEqual(assessment["overall_risk_level"], RISK_LEVEL_UNKNOWN)
        self.assertIsNone(assessment["risk_score"])
        self.assertEqual(assessment["unknown_risk_miles"], 40.0)
        self.assertEqual(assessment["data_quality"], "unavailable")


class RoutePlanningRiskIntegrationTests(APITestCase):
    """
    End-to-end integration tests for POST /api/routes/ verifying that
    risk scoring engine runs, annotates checkpoints, and produces route risk assessments.
    """

    def setUp(self):
        self.url = reverse('plan_routes')
        self.valid_payload = {
            "origin": "Chicago, IL",
            "destination": "Dallas, TX",
            "departure_datetime": "2026-10-30T08:00:00Z",
            "load_weight_lb": 45000.0,  # Heavy load > 40,000 lb
            "checkpoint_interval_miles": 50,
        }

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token'})
    @patch('requests.get')
    def test_route_planning_evaluates_risk_and_elevates_for_heavy_load(self, mock_get):
        """Verifies end-to-end route planning applies risk scoring with load weight rules."""
        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.ok = True
            resp.status_code = 200
            if "mapbox.places" in url:
                resp.json.return_value = mock_geocoding_feature()
            elif "mapbox/driving" in url:
                resp.json.return_value = {
                    "code": "Ok",
                    "routes": [mock_mapbox_route(1488000.0, 50400.0)]
                }
            elif "open-meteo" in url:
                # Wind 38.0 mph: for load 45,000 lb (> 40k), this must be elevated to Severe!
                resp.json.return_value = mock_open_meteo_forecast(
                    wind_speed=38.0,
                    precip=0.05,
                    snow=0.0,
                    temp=45.0,
                    weather_code=1,
                )
            else:
                resp.json.return_value = {}
            return resp

        mock_get.side_effect = side_effect

        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        primary = data["routes"][0]
        checkpoints = primary["checkpoints"]
        self.assertGreater(len(checkpoints), 0)

        # Checkpoints should be elevated to Severe due to wind 38 mph and load 45k lb
        cp0 = checkpoints[0]
        self.assertEqual(cp0["risk_level"], RISK_LEVEL_SEVERE)
        self.assertEqual(cp0["risk_score"], 80.0)
        self.assertIn("risk_components", cp0)
        self.assertTrue(cp0["risk_components"]["wind"]["is_elevated_by_load"])

        # Route-level risk assessment
        assessment = primary["risk_assessment"]
        self.assertEqual(assessment["overall_risk_level"], RISK_LEVEL_SEVERE)
        self.assertEqual(assessment["risk_score"], 80.0)
        self.assertGreater(assessment["severe_risk_miles"], 0.0)
        self.assertIn("SEVERE RISK", assessment["summary"])
        self.assertIn("assumptions", assessment)


def make_test_route(
    route_id: str,
    display_name: str,
    duration_seconds: int,
    distance_miles: float,
    severe_risk_miles: float = 0.0,
    high_risk_miles: float = 0.0,
    moderate_risk_miles: float = 0.0,
    low_risk_miles: float = 0.0,
    no_travel_miles: float = 0.0,
    unknown_risk_miles: float = 0.0,
    no_travel_segments_count: int = 0,
    risk_score: Optional[float] = 20.0,
    data_quality: str = "available",
) -> Dict[str, Any]:
    """Helper to construct realistic mock route objects with attached risk assessments."""
    return {
        "route_id": route_id,
        "display_name": display_name,
        "distance_miles": distance_miles,
        "distance_km": round(distance_miles * 1.60934, 1),
        "duration_seconds": duration_seconds,
        "duration_formatted": f"{duration_seconds // 3600}h {(duration_seconds % 3600) // 60}m",
        "geometry": {"type": "LineString", "coordinates": []},
        "checkpoints": [],
        "weather_summary": {},
        "risk_assessment": {
            "overall_risk_level": (
                RISK_LEVEL_NO_TRAVEL if no_travel_miles > 0
                else RISK_LEVEL_SEVERE if severe_risk_miles > 0
                else RISK_LEVEL_HIGH if high_risk_miles > 0
                else RISK_LEVEL_MODERATE if moderate_risk_miles > 0
                else RISK_LEVEL_LOW if unknown_risk_miles == 0
                else RISK_LEVEL_UNKNOWN
            ),
            "risk_score": risk_score,
            "risk_factors": [],
            "summary": "Mock route risk summary",
            "total_distance_miles": distance_miles,
            "low_risk_miles": low_risk_miles,
            "moderate_risk_miles": moderate_risk_miles,
            "high_risk_miles": high_risk_miles,
            "severe_risk_miles": severe_risk_miles,
            "no_travel_miles": no_travel_miles,
            "unknown_risk_miles": unknown_risk_miles,
            "no_travel_segments_count": no_travel_segments_count,
            "no_travel_warning": (no_travel_segments_count > 0 or no_travel_miles > 0),
            "data_quality": data_quality,
            "assumptions": [],
        },
        "recommendation": {
            "is_recommended": False,
            "status": "pending",
            "explanation": "",
        },
    }


class RouteRecommendationServiceTests(SimpleTestCase):
    """
    Automated unit tests for RouteRecommendationService verifying:
    - Independent ranking criteria (1. Severe miles, 2. High miles, 3. Avg score, 4. Duration)
    - Tie-breaking across all four criteria
    - Safety constraint for No Travel segments (route with No Travel vs without)
    - All routes containing No Travel segments
    - Incomplete / missing weather data handling
    - Stable, deterministic ordering
    - Empty and single-route edge cases
    """

    def setUp(self):
        self.service = RouteRecommendationService()

    def test_ranking_criterion_1_fewest_severe_miles(self):
        """
        Criterion 1: Fewest miles classified as Severe strictly decides ranking,
        even if the alternative has fewer high miles, lower average risk, and faster travel time.
        """
        route_a = make_test_route(
            route_id="route_a",
            display_name="Route A (Zero Severe)",
            duration_seconds=20000,
            distance_miles=200.0,
            severe_risk_miles=0.0,
            high_risk_miles=25.0,
            risk_score=40.0,
        )
        route_b = make_test_route(
            route_id="route_b",
            display_name="Route B (Fast but 10 Severe Miles)",
            duration_seconds=12000,
            distance_miles=180.0,
            severe_risk_miles=10.0,
            high_risk_miles=0.0,
            risk_score=25.0,
        )

        ranked = self.service.rank_routes([route_b, route_a])

        self.assertEqual(len(ranked), 2)
        # Route A must be ranked #1 because severe_risk_miles is 0.0 vs 10.0
        self.assertEqual(ranked[0]["route_id"], "route_a")
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertTrue(ranked[0]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[0]["recommendation"]["status"], STATUS_RECOMMENDED)

        self.assertEqual(ranked[1]["route_id"], "route_b")
        self.assertEqual(ranked[1]["rank"], 2)
        self.assertFalse(ranked[1]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[1]["recommendation"]["status"], STATUS_VIABLE_ALTERNATIVE)

    def test_ranking_criterion_2_fewest_high_risk_miles(self):
        """
        Criterion 2: When severe miles are tied, fewest miles classified as High
        decides ranking, overriding lower average score and shorter travel time.
        """
        route_a = make_test_route(
            route_id="route_a",
            display_name="Route A (Fewer High Miles)",
            duration_seconds=18000,
            distance_miles=200.0,
            severe_risk_miles=0.0,
            high_risk_miles=5.0,
            risk_score=35.0,
        )
        route_b = make_test_route(
            route_id="route_b",
            display_name="Route B (More High Miles)",
            duration_seconds=11000,
            distance_miles=180.0,
            severe_risk_miles=0.0,
            high_risk_miles=18.0,
            risk_score=25.0,
        )

        ranked = self.service.rank_routes([route_b, route_a])

        self.assertEqual(ranked[0]["route_id"], "route_a")
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertTrue(ranked[0]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[1]["route_id"], "route_b")
        self.assertEqual(ranked[1]["rank"], 2)

    def test_ranking_criterion_3_lowest_average_risk_score(self):
        """
        Criterion 3: When severe and high miles are tied, lowest average risk score
        decides ranking, overriding shorter travel time.
        """
        route_a = make_test_route(
            route_id="route_a",
            display_name="Route A (Lower Average Score)",
            duration_seconds=16000,
            distance_miles=200.0,
            severe_risk_miles=0.0,
            high_risk_miles=0.0,
            risk_score=15.0,
        )
        route_b = make_test_route(
            route_id="route_b",
            display_name="Route B (Faster but Higher Average Score)",
            duration_seconds=12000,
            distance_miles=190.0,
            severe_risk_miles=0.0,
            high_risk_miles=0.0,
            risk_score=32.0,
        )

        ranked = self.service.rank_routes([route_b, route_a])

        self.assertEqual(ranked[0]["route_id"], "route_a")
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertTrue(ranked[0]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[1]["route_id"], "route_b")
        self.assertEqual(ranked[1]["rank"], 2)

    def test_ranking_criterion_4_shortest_travel_time(self):
        """
        Criterion 4: When severe miles, high miles, and average risk score are all tied,
        shortest travel time (duration_seconds) decides ranking.
        """
        route_fast = make_test_route(
            route_id="route_fast",
            display_name="Route Fast",
            duration_seconds=10800,  # 3h 0m
            distance_miles=180.0,
            severe_risk_miles=0.0,
            high_risk_miles=0.0,
            risk_score=12.0,
        )
        route_slow = make_test_route(
            route_id="route_slow",
            display_name="Route Slow",
            duration_seconds=14400,  # 4h 0m
            distance_miles=185.0,
            severe_risk_miles=0.0,
            high_risk_miles=0.0,
            risk_score=12.0,
        )

        ranked = self.service.rank_routes([route_slow, route_fast])

        self.assertEqual(ranked[0]["route_id"], "route_fast")
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertTrue(ranked[0]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[1]["route_id"], "route_slow")
        self.assertEqual(ranked[1]["rank"], 2)

    def test_tie_breaking_across_all_four_criteria_is_deterministic(self):
        """
        When all four criteria are strictly identical, ranking must be stable
        and deterministic using route_id and sequence.
        """
        route_1 = make_test_route("route_c", "Route C", 12000, 150.0, 0.0, 0.0, risk_score=10.0)
        route_2 = make_test_route("route_a", "Route A", 12000, 150.0, 0.0, 0.0, risk_score=10.0)
        route_3 = make_test_route("route_b", "Route B", 12000, 150.0, 0.0, 0.0, risk_score=10.0)

        # Run multiple times with different initial list orders
        ranked_first = self.service.rank_routes([route_1, route_2, route_3])
        ranked_second = self.service.rank_routes([route_3, route_1, route_2])

        order_first = [r["route_id"] for r in ranked_first]
        order_second = [r["route_id"] for r in ranked_second]

        self.assertEqual(order_first, ["route_a", "route_b", "route_c"])
        self.assertEqual(order_second, ["route_a", "route_b", "route_c"])

    def test_no_travel_risk_vs_route_without_it(self):
        """
        Requirement 5: A route containing a No Travel segment must not be recommended
        as the safest route when a route without No Travel segments is available.
        """
        route_safe = make_test_route(
            route_id="route_safe",
            display_name="Route Safe (Severe but No Travel free)",
            duration_seconds=22000,
            distance_miles=250.0,
            severe_risk_miles=15.0,
            high_risk_miles=10.0,
            no_travel_miles=0.0,
            no_travel_segments_count=0,
            risk_score=65.0,
        )
        route_no_travel = make_test_route(
            route_id="route_no_travel",
            display_name="Route Unsafe (Fast but has No Travel segment)",
            duration_seconds=9000,
            distance_miles=150.0,
            severe_risk_miles=0.0,
            high_risk_miles=0.0,
            no_travel_miles=6.5,
            no_travel_segments_count=1,
            risk_score=85.0,
        )

        ranked = self.service.rank_routes([route_no_travel, route_safe])

        # Route Safe must be Rank 1 and recommended
        self.assertEqual(ranked[0]["route_id"], "route_safe")
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertTrue(ranked[0]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[0]["recommendation"]["status"], STATUS_RECOMMENDED)
        self.assertEqual(ranked[0]["recommendation"]["eligibility"], ELIGIBILITY_ELIGIBLE)

        # Route No Travel must be Rank 2, NOT recommended, and flagged
        self.assertEqual(ranked[1]["route_id"], "route_no_travel")
        self.assertEqual(ranked[1]["rank"], 2)
        self.assertFalse(ranked[1]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[1]["recommendation"]["status"], STATUS_NOT_RECOMMENDED)
        self.assertEqual(ranked[1]["recommendation"]["eligibility"], ELIGIBILITY_NO_TRAVEL)
        self.assertIn("NOT RECOMMENDED", ranked[1]["recommendation"]["explanation"])
        self.assertIn("6.5 miles of No Travel", ranked[1]["recommendation"]["explanation"])

    def test_every_route_contains_no_travel_segments(self):
        """
        Requirement 5: If every route contains a No Travel segment, clearly flag
        that no route is considered safe and explain why.
        """
        route_1 = make_test_route(
            route_id="route_1",
            display_name="Route 1",
            duration_seconds=12000,
            distance_miles=200.0,
            no_travel_miles=4.0,
            no_travel_segments_count=1,
        )
        route_2 = make_test_route(
            route_id="route_2",
            display_name="Route 2",
            duration_seconds=11000,
            distance_miles=190.0,
            no_travel_miles=12.5,
            no_travel_segments_count=2,
        )

        ranked = self.service.rank_routes([route_1, route_2])
        summary = self.service.build_recommendation_summary(ranked)

        # Neither route may be marked recommended
        self.assertFalse(ranked[0]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[0]["recommendation"]["status"], STATUS_NOT_RECOMMENDED)
        self.assertFalse(ranked[1]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[1]["recommendation"]["status"], STATUS_NOT_RECOMMENDED)

        # Ranked by fewest No Travel miles (4.0 < 12.5)
        self.assertEqual(ranked[0]["route_id"], "route_1")
        self.assertEqual(ranked[1]["route_id"], "route_2")

        # Top-level summary flags all routes unsafe
        self.assertTrue(summary["all_routes_unsafe"])
        self.assertIsNone(summary["recommended_route_id"])
        self.assertIn("NO SAFE ROUTE AVAILABLE", summary["executive_summary"])

    def test_incomplete_weather_data_never_silently_beats_fully_assessed_route(self):
        """
        Requirement 6: A route with unknown risk must not silently be treated
        as safer than a fully assessed route.
        """
        route_complete = make_test_route(
            route_id="route_complete",
            display_name="Route Complete Assessment",
            duration_seconds=18000,
            distance_miles=200.0,
            severe_risk_miles=2.0,
            high_risk_miles=0.0,
            unknown_risk_miles=0.0,
            risk_score=25.0,
            data_quality="available",
        )
        route_incomplete = make_test_route(
            route_id="route_incomplete",
            display_name="Route Incomplete Assessment",
            duration_seconds=10000,
            distance_miles=180.0,
            severe_risk_miles=0.0,
            high_risk_miles=0.0,
            unknown_risk_miles=80.0,
            risk_score=None,
            data_quality="partial",
        )

        ranked = self.service.rank_routes([route_incomplete, route_complete])

        # Fully assessed route must be ranked #1
        self.assertEqual(ranked[0]["route_id"], "route_complete")
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertTrue(ranked[0]["recommendation"]["is_recommended"])

        # Incomplete route ranked #2 and flagged
        self.assertEqual(ranked[1]["route_id"], "route_incomplete")
        self.assertEqual(ranked[1]["rank"], 2)
        self.assertFalse(ranked[1]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[1]["recommendation"]["status"], STATUS_NOT_RECOMMENDED)
        self.assertEqual(ranked[1]["recommendation"]["assessment_status"], ASSESSMENT_PARTIAL)
        self.assertEqual(ranked[1]["recommendation"]["eligibility"], ELIGIBILITY_INCOMPLETE)
        self.assertIn("incomplete weather data", ranked[1]["recommendation"]["explanation"])

    def test_all_routes_incomplete_weather_data_flags_data_quality_caveat(self):
        """
        When all available routes lack complete weather data, the service recommends
        the fastest route while explicitly warning of missing weather forecasts.
        """
        route_1 = make_test_route(
            route_id="route_1",
            display_name="Route 1",
            duration_seconds=10000,
            distance_miles=200.0,
            unknown_risk_miles=200.0,
            risk_score=None,
            data_quality="unavailable",
        )
        route_2 = make_test_route(
            route_id="route_2",
            display_name="Route 2",
            duration_seconds=14000,
            distance_miles=220.0,
            unknown_risk_miles=220.0,
            risk_score=None,
            data_quality="unavailable",
        )

        ranked = self.service.rank_routes([route_2, route_1])
        summary = self.service.build_recommendation_summary(ranked)

        self.assertEqual(ranked[0]["route_id"], "route_1")
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertTrue(ranked[0]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[0]["recommendation"]["assessment_status"], ASSESSMENT_UNAVAILABLE)
        self.assertIn("CAUTION", ranked[0]["recommendation"]["explanation"])

        self.assertEqual(ranked[1]["route_id"], "route_2")
        self.assertFalse(ranked[1]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[1]["recommendation"]["status"], STATUS_VIABLE_ALTERNATIVE)

        self.assertTrue(summary["incomplete_data_warning"])

    def test_single_available_route_eligible(self):
        """Single available safe route is ranked #1 and recommended."""
        route = make_test_route(
            route_id="only_route",
            display_name="Only Route",
            duration_seconds=14400,
            distance_miles=210.0,
            severe_risk_miles=0.0,
            high_risk_miles=0.0,
            risk_score=15.0,
        )

        ranked = self.service.rank_routes([route])
        summary = self.service.build_recommendation_summary(ranked)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertTrue(ranked[0]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[0]["recommendation"]["status"], STATUS_RECOMMENDED)
        self.assertEqual(summary["recommended_route_id"], "only_route")
        self.assertEqual(summary["total_options_evaluated"], 1)

    def test_single_available_route_with_no_travel_ineligible(self):
        """Single available route that encounters No Travel must not be recommended."""
        route = make_test_route(
            route_id="hazardous_route",
            display_name="Hazardous Route",
            duration_seconds=14400,
            distance_miles=210.0,
            no_travel_miles=8.0,
            no_travel_segments_count=1,
            risk_score=90.0,
        )

        ranked = self.service.rank_routes([route])
        summary = self.service.build_recommendation_summary(ranked)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertFalse(ranked[0]["recommendation"]["is_recommended"])
        self.assertEqual(ranked[0]["recommendation"]["status"], STATUS_NOT_RECOMMENDED)
        self.assertTrue(summary["all_routes_unsafe"])
        self.assertIsNone(summary["recommended_route_id"])

    def test_empty_route_list_returns_cleanly(self):
        """Empty route lists must be handled cleanly without errors."""
        ranked = self.service.rank_routes([])
        summary = self.service.build_recommendation_summary([])

        self.assertEqual(ranked, [])
        self.assertIsNone(summary["recommended_route_id"])
        self.assertEqual(summary["total_options_evaluated"], 0)
        self.assertFalse(summary["all_routes_unsafe"])
        self.assertIn("No route options", summary["executive_summary"])

    def test_top_level_recommendation_summary_fields(self):
        """Verifies top-level recommendation summary includes required policies and priority rules."""
        route = make_test_route("r1", "Route 1", 10000, 100.0)
        ranked = self.service.rank_routes([route])
        summary = self.service.build_recommendation_summary(ranked)

        self.assertIn("recommended_route_id", summary)
        self.assertIn("all_routes_unsafe", summary)
        self.assertIn("incomplete_data_warning", summary)
        self.assertIn("ranking_priority", summary)
        self.assertEqual(len(summary["ranking_priority"]), 4)
        self.assertIn("Fewest miles classified as Severe", summary["ranking_priority"][0])
        self.assertIn("safety_policy", summary)
        self.assertIn("data_quality_policy", summary)
        self.assertIn("executive_summary", summary)


class RoutePlanningRecommendationIntegrationTests(APITestCase):
    """
    End-to-end integration tests for POST /api/routes/ verifying that
    lexicographic route ranking and recommendations are included in the API response.
    """

    def setUp(self):
        self.url = reverse('plan_routes')
        self.valid_payload = {
            "origin": "Chicago, IL",
            "destination": "Dallas, TX",
            "departure_datetime": "2026-10-30T08:00:00Z",
            "load_weight_lb": 35000.0,
            "checkpoint_interval_miles": 50,
        }

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token'})
    @patch('requests.get')
    def test_route_planning_ranks_and_recommends_safest_route(self, mock_get):
        """Verifies end-to-end route planning ranks routes and produces recommendation_summary."""
        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.ok = True
            resp.status_code = 200
            if "mapbox.places" in url:
                resp.json.return_value = mock_geocoding_feature()
            elif "mapbox/driving" in url:
                resp.json.return_value = {
                    "code": "Ok",
                    "routes": [
                        mock_mapbox_route(1488000.0, 50400.0, "Route A - Calm"),
                        mock_mapbox_route(1520000.0, 48000.0, "Route B - Windy"),
                    ]
                }
            elif "open-meteo" in url:
                # Provide favorable weather
                resp.json.return_value = mock_open_meteo_forecast(
                    wind_speed=12.0,
                    precip=0.01,
                    snow=0.0,
                    temp=55.0,
                    weather_code=1,
                )
            else:
                resp.json.return_value = {}
            return resp

        mock_get.side_effect = side_effect

        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["status"], "planned")
        self.assertIn("recommendation_summary", data)
        rec_summary = data["recommendation_summary"]
        self.assertIsNotNone(rec_summary["recommended_route_id"])
        self.assertEqual(len(rec_summary["ranking_priority"]), 4)

        routes = data["routes"]
        self.assertEqual(len(routes), 2)
        # Route 1 (Rank 1)
        r1 = routes[0]
        self.assertEqual(r1["rank"], 1)
        self.assertTrue(r1["recommendation"]["is_recommended"])
        self.assertEqual(r1["recommendation"]["status"], STATUS_RECOMMENDED)
        self.assertIn("ranking_metrics", r1["recommendation"])

        # Route 2 (Rank 2)
        r2 = routes[1]
        self.assertEqual(r2["rank"], 2)
        self.assertFalse(r2["recommendation"]["is_recommended"])
        self.assertEqual(r2["recommendation"]["status"], STATUS_VIABLE_ALTERNATIVE)

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token'})
    @patch('requests.get')
    def test_route_planning_all_routes_encounter_no_travel_advisories(self, mock_get):
        """Verifies end-to-end that when extreme weather enforces No Travel on all routes, all_routes_unsafe is set."""
        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.ok = True
            resp.status_code = 200
            if "mapbox.places" in url:
                resp.json.return_value = mock_geocoding_feature()
            elif "mapbox/driving" in url:
                resp.json.return_value = {
                    "code": "Ok",
                    "routes": [
                        mock_mapbox_route(1488000.0, 50400.0, "Route A - Extreme"),
                        mock_mapbox_route(1520000.0, 48000.0, "Route B - Extreme"),
                    ]
                }
            elif "open-meteo" in url:
                # 60 mph wind triggers No Travel on all segments
                resp.json.return_value = mock_open_meteo_forecast(
                    wind_speed=60.0,
                    precip=0.0,
                    snow=0.0,
                )
            else:
                resp.json.return_value = {}
            return resp

        mock_get.side_effect = side_effect

        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        rec_summary = data["recommendation_summary"]
        self.assertTrue(rec_summary["all_routes_unsafe"])
        self.assertIsNone(rec_summary["recommended_route_id"])
        self.assertIn("NO SAFE ROUTE AVAILABLE", rec_summary["executive_summary"])

        for route in data["routes"]:
            self.assertFalse(route["recommendation"]["is_recommended"])
            self.assertEqual(route["recommendation"]["status"], STATUS_NOT_RECOMMENDED)
            self.assertTrue(route["risk_assessment"]["no_travel_warning"])

    @patch.dict('os.environ', {'MAPBOX_ACCESS_TOKEN': 'pk.mock-token'})
    @patch('requests.get')
    def test_route_planning_preserves_missing_weather_as_unknown_never_low(self, mock_get):
        """Verifies end-to-end that missing weather data is preserved as Unknown and never treated as Low risk."""
        def side_effect(url, **kwargs):
            resp = MagicMock()
            resp.ok = True
            resp.status_code = 200
            if "mapbox.places" in url:
                resp.json.return_value = mock_geocoding_feature()
            elif "mapbox/driving" in url:
                resp.json.return_value = {
                    "code": "Ok",
                    "routes": [
                        mock_mapbox_route(1488000.0, 50400.0, "Route With Missing Weather"),
                    ]
                }
            elif "open-meteo" in url:
                # Empty hourly arrays simulating weather provider missing measurements
                resp.json.return_value = {
                    "latitude": 41.8781,
                    "longitude": -87.6298,
                    "hourly": {
                        "time": ["2026-10-30T08:00"],
                        "temperature_2m": [None],
                        "precipitation": [None],
                        "snowfall": [None],
                        "weather_code": [None],
                        "wind_speed_10m": [None],
                        "wind_gusts_10m": [None],
                    }
                }
            else:
                resp.json.return_value = {}
            return resp

        mock_get.side_effect = side_effect

        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        route = data["routes"][0]
        # Checkpoint risk level must be unknown, NOT low
        for cp in route["checkpoints"]:
            self.assertEqual(cp["risk_level"], "unknown")
            self.assertIsNone(cp["risk_score"])
        # Overall risk level must be unknown, NOT low
        self.assertEqual(route["risk_assessment"]["overall_risk_level"], "unknown")
        self.assertIsNone(route["risk_assessment"]["risk_score"])









