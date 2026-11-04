__version__ = "1.0.1"

from .celery import app as celery_app

__all__ = ["celery_app"]
