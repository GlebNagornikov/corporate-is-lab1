from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase, override_settings
from django.urls import reverse

from config import __version__


class HealthCheckTests(TestCase):
    def test_health_checks_database_and_returns_version_without_login(self):
        with self.assertNumQueries(1):
            response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "version": __version__})

    def test_unavailable_database_does_not_report_healthy(self):
        with patch("config.health.connection.cursor", side_effect=OperationalError("unavailable")):
            with self.assertRaises(OperationalError):
                self.client.get(reverse("healthz"))

    @override_settings(
        SECURE_SSL_REDIRECT=True,
        SECURE_REDIRECT_EXEMPT=[r"^healthz/$"],
    )
    def test_internal_http_health_check_is_exempt_but_other_paths_redirect(self):
        self.assertEqual(self.client.get(reverse("healthz")).status_code, 200)
        self.assertEqual(self.client.get("/").status_code, 301)
