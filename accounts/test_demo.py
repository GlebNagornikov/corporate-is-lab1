import tempfile
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from catalog.models import Product, ProductVariant
from orders.models import PromoCode


class DemoSetupTests(TestCase):
    def test_expired_legacy_promo_is_preserved_and_separate_demo_code_created(self):
        now = timezone.now()
        promo = PromoCode.objects.create(
            code="STUDENT10",
            discount_percent=15,
            valid_from=now - timedelta(days=20),
            valid_until=now - timedelta(days=1),
        )
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            call_command("setup_demo", password="Demonstration123!", stdout=StringIO())
        promo.refresh_from_db()
        self.assertFalse(promo.is_valid_now())
        self.assertEqual(promo.discount_percent, 15)
        self.assertTrue(PromoCode.objects.get(code="CHECKPOINT10").is_valid_now())

    def test_demo_setup_is_idempotent_and_does_not_reset_password(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            call_command("setup_demo", password="Demonstration123!", stdout=StringIO())
            call_command("setup_demo", password="AnotherPassword123!", stdout=StringIO())
        self.assertEqual(Product.objects.count(), 5)
        self.assertEqual(ProductVariant.objects.count(), 10)
        self.assertTrue(User.objects.get(username="buyer_demo").check_password("Demonstration123!"))
        manager = User.objects.get(username="manager_demo")
        self.assertTrue(manager.has_perm("catalog.change_productvariant"))
        self.assertFalse(manager.is_superuser)

    def test_short_password_rejected_without_changes(self):
        with self.assertRaises(CommandError):
            call_command("setup_demo", password="short", stdout=StringIO())
        self.assertFalse(User.objects.exists())

    def test_existing_account_with_different_role_is_preserved(self):
        user = User.objects.create_user("buyer_demo", is_staff=True)
        with self.assertRaises(CommandError):
            call_command("setup_demo", password="Demonstration123!", stdout=StringIO())
        user.refresh_from_db()
        self.assertTrue(user.is_staff)
