#!/bin/sh
set -eu

SUPPORT_PHONE=${SUPPORT_PHONE:-'+7 800 555-35-35'}
case "$SUPPORT_PHONE" in
  *[!0-9+\ \(\)-]*) echo 'Invalid SUPPORT_PHONE' >&2; exit 1 ;;
esac
export SUPPORT_PHONE
envsubst '${SUPPORT_PHONE}' < /etc/nginx/config.js.template > /usr/share/nginx/html/config.js
