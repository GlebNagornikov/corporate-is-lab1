import json
import logging
import re
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

context = ContextVar("request_logging", default=None)


def request_id():
    return (context.get() or {}).get("request_id", "")


class RequestIDMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        identifier = (
            incoming if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", incoming) else uuid.uuid4().hex
        )
        request.request_id = identifier
        token = context.set({"request_id": identifier, "request": request})
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = identifier
            logging.getLogger("requests").info(
                "HTTP request",
                extra={"status_code": response.status_code, "method": request.method},
            )
            return response
        finally:
            context.reset(token)


class JSONFormatter(logging.Formatter):
    def format(self, record):
        current = context.get() or {}
        request = current.get("request")
        user = getattr(request, "user", None)
        fields = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": current.get("request_id", ""),
            "user_id": getattr(user, "pk", None),
            "path": getattr(request, "path", ""),
        }
        for key in ("order_id", "notification_id", "status_code", "method", "task_id"):
            if hasattr(record, key):
                fields[key] = getattr(record, key)
        if record.exc_info:
            fields["exception"] = self.formatException(record.exc_info)
        return json.dumps(fields, ensure_ascii=False, default=str)
