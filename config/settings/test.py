from .base import *  # noqa: F401,F403

# Только для тестов: рабочие настройки сохраняют безопасные хешеры паролей.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
TEST_RUNNER = "config.test_runner.IsolatedCacheRunner"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False
