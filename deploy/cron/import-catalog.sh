#!/usr/bin/env bash
# Cron-friendly WP catalog sync for moziketo-hand.
# Install: 0 */6 * * * /opt/moziketo/cron/import-catalog.sh >> /var/log/moziketo-import.log 2>&1
set -euo pipefail

ENV_FILE="${WAVE_ENV_FILE:-/opt/moziketo/wave.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${ADMIN_API_KEY:?ADMIN_API_KEY missing in wave.env}"

API_BASE="${OAUTH_API_BASE_URL:-https://api.moziketo.ir/api/v1}"
response=$(curl -sf -X POST "${API_BASE%/}/admin/import?limit=0" \
  -H "X-Admin-Key: ${ADMIN_API_KEY}" \
  -w "\n%{http_code}")
body=$(echo "$response" | head -n -1)
code=$(echo "$response" | tail -n 1)
echo "HTTP ${code}: ${body}"
if [[ "$code" != "202" && "$code" != "200" ]]; then
  exit 1
fi
