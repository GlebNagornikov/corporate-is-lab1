import socket

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
# LOGGING["loggers"]["django.db.backends"] = {
# "handlers": ["console"],
# "level": "DEBUG",
# "propagate": False,
# }
INSTALLED_APPS += ["debug_toolbar", "corsheaders"]
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
MIDDLEWARE.insert(0, "corsheaders.middleware.CorsMiddleware")
CORS_ALLOWED_ORIGINS = env.list(
    "DEV_CORS_ALLOWED_ORIGINS", default=["http://localhost:5173", "http://127.0.0.1:5173"]
)
CORS_URLS_REGEX = r"^/api/(?!auth/session/)"

# В Docker запросы браузера приходят не с 127.0.0.1, а со шлюза docker-сети (x.x.x.1)
_, _, _ips = socket.gethostbyname_ex(socket.gethostname())
INTERNAL_IPS = ["127.0.0.1"] + [ip[: ip.rfind(".")] + ".1" for ip in _ips]
