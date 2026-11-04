FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --uid 1000 --create-home app
WORKDIR /app

FROM base AS dev
COPY requirements/ requirements/
RUN pip install -r requirements/dev.txt

COPY . .

RUN chown -R app:app /app
USER app

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS builder
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements/ requirements/
RUN pip install -r requirements/base.txt

FROM base AS prod
ENV PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod
COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app . .
RUN mkdir -p staticfiles media && chown app:app staticfiles media \
    && chmod +x /app/docker/entrypoint.sh
USER app
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "-c", "docker/gunicorn.conf.py"]
