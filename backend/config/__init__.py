__version__ = "2.0.0"

from .celery import app as celery_app

__all__ = ["celery_app"]
