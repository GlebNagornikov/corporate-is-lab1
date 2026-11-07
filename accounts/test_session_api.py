from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient


class CookieSessionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        get_user_model().objects.create_user("cookie-buyer", password="Long-test-password")

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.csrf = self.client.get("/api/auth/session/csrf/", secure=True).data["csrf_token"]

    def post(self, action, data=None, *, csrf=True, origin="https://testserver"):
        headers = {"HTTP_X_CSRFTOKEN": self.csrf} if csrf else {}
        return self.client.post(
            f"/api/auth/session/{action}/",
            data,
            format="json",
            secure=True,
            HTTP_ORIGIN=origin,
            **headers,
        )

    def test_cookie_login_refresh_and_logout(self):
        login = self.post("login", {"username": "cookie-buyer", "password": "Long-test-password"})
        self.assertEqual(login.status_code, 200)
        self.assertEqual(set(login.data), {"access"})
        cookie = login.cookies["shop_refresh"]
        self.assertTrue(cookie["httponly"])
        self.assertTrue(cookie["secure"])
        self.assertEqual(cookie["samesite"], "Strict")
        self.assertEqual(cookie["path"], "/api/auth/")
        self.assertIn("no-store", login["Cache-Control"])

        self.assertEqual(self.post("refresh", csrf=False).status_code, 403)
        self.assertEqual(self.post("refresh", origin="https://other.test").status_code, 403)
        renewed = self.post("refresh")
        self.assertEqual(renewed.status_code, 200)
        self.assertEqual(set(renewed.data), {"access"})
        profile = self.client.get(
            "/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {renewed.data['access']}"
        )
        self.assertEqual(profile.data["username"], "cookie-buyer")

        self.assertEqual(self.post("logout", csrf=False).status_code, 403)
        logout = self.post("logout")
        self.assertEqual(logout.status_code, 204)
        self.assertEqual(logout.cookies["shop_refresh"]["max-age"], 0)
        self.assertEqual(logout.cookies["shop_refresh"]["path"], "/api/auth/")
        self.assertEqual(self.post("refresh").status_code, 401)

    def test_login_requires_csrf_and_keeps_wrong_credentials_at_401(self):
        credentials = {"username": "cookie-buyer", "password": "wrong"}
        self.assertEqual(self.post("login", credentials, csrf=False).status_code, 403)
        response = self.post("login", credentials)
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("shop_refresh", response.cookies)
