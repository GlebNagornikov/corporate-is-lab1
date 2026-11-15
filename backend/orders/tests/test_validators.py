from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase

from orders.forms import CheckoutForm
from orders.serializers import CheckoutSerializer
from orders.validators import normalize_phone


class NormalizePhoneTests(SimpleTestCase):
    def test_different_formats_give_one_result(self):
        for raw in ["+7 913 123-45-67", "8 (913) 123-45-67", "89131234567", "9131234567"]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_phone(raw), "+79131234567")

    def test_garbage_is_rejected(self):
        for raw in ["", "123", "+1 202 555 0100", "телефон", "звонить после 18"]:
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                normalize_phone(raw)


class CheckoutPhoneTests(TestCase):
    def test_form_and_api_share_normalization_and_field_errors(self):
        data = {
            "full_name": "Покупатель",
            "phone": "8 (913) 555-12-34",
            "email": "buyer@example.test",
            "delivery_method": "pickup",
        }
        form = CheckoutForm(data=data)
        serializer = CheckoutSerializer(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(form.cleaned_data["phone"], "+79135551234")
        self.assertEqual(serializer.validated_data["phone"], "+79135551234")
        data["phone"] = "123"
        form = CheckoutForm(data=data)
        serializer = CheckoutSerializer(data=data)
        self.assertFalse(form.is_valid())
        self.assertFalse(serializer.is_valid())
        self.assertIn("phone", form.errors)
        self.assertIn("phone", serializer.errors)
