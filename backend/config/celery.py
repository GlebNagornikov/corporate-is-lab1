import os

from celery import Celery
from celery.signals import after_setup_logger, after_setup_task_logger, task_postrun, task_prerun

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
app = Celery("shop")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@after_setup_logger.connect
@after_setup_task_logger.connect
def configure_task_logs(logger, **kwargs):
    from .request_logging import JSONFormatter

    for handler in logger.handlers:
        handler.setFormatter(JSONFormatter())


@task_prerun.connect
def task_context(task=None, **kwargs):
    from .request_logging import context

    headers = task.request.headers or {}
    task.request.log_context_token = context.set({"request_id": headers.get("request_id", "")})


@task_postrun.connect
def clear_task_context(task=None, **kwargs):
    from .request_logging import context

    token = getattr(task.request, "log_context_token", None)
    if token is not None:
        context.reset(token)
