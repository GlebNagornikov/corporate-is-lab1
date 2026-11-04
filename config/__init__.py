__version__ = "1.1.1"

from .celery import app as celery_app

__all__ = ["celery_app"]
