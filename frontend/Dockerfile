# Контекст сборки — корень репозитория.
FROM node:24-slim AS build
WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./

ARG APP_VERSION=dev
ENV VITE_APP_VERSION=$APP_VERSION
RUN npm run build

FROM nginx:1.29-alpine AS prod
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
