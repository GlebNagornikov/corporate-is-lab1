from unittest import TextTestResult, TextTestRunner

from django.core.cache import caches
from django.test.runner import DiscoverRunner


class CacheResult(TextTestResult):
    def startTest(self, test):
        for cache in caches.all():
            cache.clear()
        super().startTest(test)


class CacheRunner(TextTestRunner):
    resultclass = CacheResult


class IsolatedCacheRunner(DiscoverRunner):
    test_runner = CacheRunner
