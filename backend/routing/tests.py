from datetime import datetime, timedelta, timezone
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
)


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






