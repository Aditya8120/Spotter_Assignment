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
)


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




