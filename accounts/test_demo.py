import tempfile
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from accounts.models import User
from catalog.models import Product, ProductVariant


class DemoSetupTests(TestCase):
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
