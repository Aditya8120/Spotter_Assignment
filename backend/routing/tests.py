from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase





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


