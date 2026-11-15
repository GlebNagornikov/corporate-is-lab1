from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from drf_spectacular.generators import SchemaGenerator
from rest_framework.test import APIClient


class OpenAPIContractTests(SimpleTestCase):
    def test_schema_validates_without_warnings(self):
        schema = StringIO()
        call_command("spectacular", "--validate", "--fail-on-warn", stdout=schema)
        self.assertTrue(schema.getvalue())

    def test_order_status_action_documents_its_request_body(self):
        schema = SchemaGenerator().get_schema(public=True)
        action = schema["paths"]["/api/orders/{id}/status/"]["post"]
        self.assertEqual(
            action["requestBody"]["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/StatusChangeRequest",
        )

    def test_manager_catalog_documents_binary_cover_and_access_errors(self):
        schema = SchemaGenerator().get_schema(public=True)
        for path, method in (
            ("/api/manager/catalog/", "post"),
            ("/api/manager/catalog/{id}/", "patch"),
        ):
            action = schema["paths"][path][method]
            payload = action["requestBody"]["content"]["multipart/form-data"]["schema"]
            name = payload["$ref"].rsplit("/", 1)[-1]
            cover = schema["components"]["schemas"][name]["properties"]["image"]
            self.assertEqual(cover["format"], "binary")
            self.assertIn("401", action["responses"])
            self.assertIn("403", action["responses"])


class APIDocsTests(TestCase):
    def test_eleventh_token_request_is_throttled(self):
        client = APIClient()
        for _ in range(10):
            self.assertEqual(
                client.post(
                    "/api/auth/token/", {"username": "missing", "password": "wrong"}
                ).status_code,
                401,
            )
        response = client.post("/api/auth/token/", {"username": "missing", "password": "wrong"})
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)

    @override_settings(DEBUG=False)
    def test_production_docs_require_staff(self):
        user = get_user_model().objects.create_user("customer")
        self.client.force_login(user)
        self.assertEqual(self.client.get("/api/docs/").status_code, 403)
        user.is_staff = True
        user.save()
        self.assertEqual(self.client.get("/api/docs/").status_code, 200)

    def test_schema_contains_all_api_groups(self):
        schema = SchemaGenerator().get_schema(public=True)
        for path in [
            "/api/cart/",
            "/api/cart/merge/",
            "/api/orders/",
            "/api/catalog/products/",
            "/api/wishlist/",
            "/api/employees/",
            "/api/auth/token/",
            "/api/auth/register/",
            "/api/auth/me/",
        ]:
            self.assertIn(path, schema["paths"])
            self.assertTrue(next(iter(schema["paths"][path].values()))["description"])
