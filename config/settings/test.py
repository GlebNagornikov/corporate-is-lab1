from .base import *  # noqa: F401,F403

# Только для тестов: рабочие настройки сохраняют безопасные хешеры паролей.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
