import os

bind = "0.0.0.0:8000"
worker_class = "asgi"
asgi_lifespan = "off"
workers = int(os.environ.get("GUNICORN_WORKERS", 3))
timeout = 30
accesslog = "-"
errorlog = "-"
