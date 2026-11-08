from django.core.cache import caches
from django.core.cache.backends.locmem import LocMemCache
from redis.exceptions import RedisError
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle

fallback = LocMemCache("throttle-fallback", {})


class ThrottleCache:
    def get(self, key, default=None):
        try:
            return caches["throttles"].get(key, default)
        except (RedisError, OSError):
            return fallback.get(key, default)

    def set(self, key, value, timeout):
        try:
            return caches["throttles"].set(key, value, timeout)
        except (RedisError, OSError):
            return fallback.set(key, value, timeout)


class ShopAnonThrottle(AnonRateThrottle):
    cache = ThrottleCache()


class ShopUserThrottle(UserRateThrottle):
    cache = ThrottleCache()


class TokenThrottle(SimpleRateThrottle):
    scope = "token"
    cache = ThrottleCache()

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
