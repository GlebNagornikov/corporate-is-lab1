import os
import subprocess
import sys

from django.test import SimpleTestCase


class ProductionSettingsTests(SimpleTestCase):
    def test_production_keeps_smtp_options_and_secure_password_hashers(self):
        env = {
            **os.environ,
            "ALLOWED_HOSTS": "localhost",
            "EMAIL_HOST": "smtp.example.test",
            "EMAIL_PORT": "2525",
        }
        code = (
            "import config.settings.prod as s; "
            "assert s.MAILERS['default']['OPTIONS']['host'] == 'smtp.example.test'; "
            "assert s.MAILERS['default']['OPTIONS']['port'] == 2525; "
            "assert not any('MD5' in h for h in getattr(s, 'PASSWORD_HASHERS', []))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=False
        )
        self.assertEqual(result.returncode, 0, result.stderr)
