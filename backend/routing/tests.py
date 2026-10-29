from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .serializers import (
    RoutePlanRequestSerializer,
    RoutePlanResponseSerializer,
)


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


class RoutePlanningAPITests(APITestCase):
    def setUp(self):
        self.url = reverse('plan_routes')
        self.valid_payload = {
            "origin": "Chicago, IL",
            "destination": "Dallas, TX",
            "departure_datetime": "2026-10-30T08:00:00Z",
            "load_weight_lb": 35000.0,
        }

    def test_valid_request_with_text_locations(self):
        response = self.client.post(self.url, self.valid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "not_implemented")
        self.assertIn("request_summary", data)
        self.assertEqual(data["request_summary"]["load_weight_lb"], 35000.0)
        self.assertEqual(data["request_summary"]["origin"], "Chicago, IL")
        self.assertEqual(data["request_summary"]["destination"], "Dallas, TX")
        self.assertEqual(data["routes"], [])

    def test_valid_request_with_coordinate_dict_locations(self):
        payload = {
            "origin": {"latitude": 41.8781, "longitude": -87.6298},
            "destination": {"latitude": 32.7767, "longitude": -96.7970},
            "departure_datetime": "2026-10-30T08:00:00Z",
            "load_weight_lb": 42000.5,
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "not_implemented")
        self.assertEqual(data["request_summary"]["origin"]["latitude"], 41.8781)
        self.assertEqual(data["request_summary"]["origin"]["longitude"], -87.6298)

    def test_valid_request_with_coordinate_strings(self):
        payload = {
            "origin": "41.8781, -87.6298",
            "destination": "32.7767, -96.7970",
            "departure_datetime": "2026-10-30T08:00:00Z",
            "load_weight_lb": 25000,
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(data["status"], "not_implemented")
        self.assertEqual(data["request_summary"]["origin"]["latitude"], 41.8781)

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

    def test_cors_on_routes_endpoint(self):
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
                    "route_id": "route-primary-i55",
                    "display_name": "I-55 S to I-30 W (Recommended)",
                    "distance_miles": 925.4,
                    "duration_seconds": 51600,
                    "duration_formatted": "14h 20m",
                    "checkpoints": [
                        {
                            "sequence": 1,
                            "name": "Chicago Origin",
                            "latitude": 41.8781,
                            "longitude": -87.6298,
                            "estimated_arrival": "2026-10-30T08:00:00Z",
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
                            "name": "St. Louis Waypoint",
                            "latitude": 38.6270,
                            "longitude": -90.1994,
                            "estimated_arrival": "2026-10-30T13:30:00Z",
                            "distance_from_origin_miles": 297.0,
                            "duration_from_origin_seconds": 16200,
                            "weather": {
                                "temperature": 55.0,
                                "condition": "Moderate Rain",
                                "wind_speed_mph": 20.0,
                                "wind_gust_mph": 32.0,
                                "precipitation_probability": 75.0,
                                "visibility_miles": 6.0,
                                "units": {
                                    "temperature": "°F",
                                    "wind_speed": "mph",
                                    "precipitation": "%",
                                    "visibility": "miles"
                                }
                            },
                            "risk_level": "moderate",
                            "risk_summary": "Wet pavement and gusty crosswinds."
                        }
                    ],
                    "weather_summary": {
                        "max_wind_speed_mph": 20.0,
                        "adverse_conditions": ["Moderate Rain"]
                    },
                    "risk_assessment": {
                        "overall_risk_level": "moderate",
                        "risk_score": 35.0,
                        "risk_factors": ["Moderate Rain in St. Louis corridor"],
                        "summary": "Manageable route with cautious driving in rain."
                    },
                    "recommendation": {
                        "is_recommended": True,
                        "status": "recommended",
                        "explanation": "Best balance of transit time and mild weather risks."
                    }
                }
            ]
        }

        serializer = RoutePlanResponseSerializer(data=mock_data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(len(serializer.validated_data["routes"]), 1)
        route = serializer.validated_data["routes"][0]
        self.assertEqual(route["route_id"], "route-primary-i55")
        self.assertEqual(route["recommendation"]["status"], "recommended")
        self.assertEqual(len(route["checkpoints"]), 2)



