from django.test import TestCase
from rest_framework.test import APIClient


class TestHealthEndpoint(TestCase):
    def test_health_returns_ok_without_auth(self):
        response = APIClient().get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "ok")
