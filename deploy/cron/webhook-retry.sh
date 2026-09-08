#!/usr/bin/env bash
# Retry pending/failed webhook deliveries via wave worker.
# Install: */5 * * * * /opt/moziketo/cron/webhook-retry.sh >> /var/log/moziketo-webhooks.log 2>&1
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
response=$(curl -sf -X POST "${API_BASE%/}/admin/jobs/webhooks/retry" \
  -H "X-Admin-Key: ${ADMIN_API_KEY}" \
  -w "\n%{http_code}")
body=$(echo "$response" | head -n -1)
code=$(echo "$response" | tail -n 1)
echo "HTTP ${code}: ${body}"
if [[ "$code" != "202" ]]; then
  exit 1
fi
