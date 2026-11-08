import time

from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django_redis.cache import RedisCache
from redis.exceptions import RedisError


class ResilientRedisCache(RedisCache):
    """Skip repeated network attempts briefly after Redis becomes unavailable."""

    unavailable_until = 0

    def _call(self, operation, fallback, *args, **kwargs):
        if time.monotonic() < self.unavailable_until:
            return fallback
        try:
            return operation(*args, **kwargs)
        except (RedisError, OSError):
            self.unavailable_until = time.monotonic() + 5
            return fallback

    def get(self, key, default=None, version=None):
        return self._call(super().get, default, key, default=default, version=version)

    def set(self, key, value, timeout=DEFAULT_TIMEOUT, version=None, **kwargs):
        return self._call(
            super().set, False, key, value, timeout=timeout, version=version, **kwargs
        )

    def delete(self, key, version=None):
        return self._call(super().delete, False, key, version=version)
