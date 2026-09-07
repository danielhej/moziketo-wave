#!/usr/bin/env bash
# Update OAuth credentials on moziketo-hand (/opt/moziketo/wave.env) and restart wave.
#
# Usage:
#   GOOGLE_CLIENT_ID=... GOOGLE_CLIENT_SECRET=... \
#   GITHUB_CLIENT_ID=... GITHUB_CLIENT_SECRET=... \
#   ./scripts/configure_oauth_production.sh
#
# Or load from ~/.cursor/skills/moziketo-access/oauth.env:
#   source ~/.cursor/skills/moziketo-access/oauth.env && ./scripts/configure_oauth_production.sh
set -euo pipefail

if [[ -z "${GOOGLE_CLIENT_ID:-}" && -f "${HOME}/.cursor/skills/moziketo-access/oauth.env" ]]; then
  # shellcheck disable=SC1091
  source "${HOME}/.cursor/skills/moziketo-access/oauth.env"
fi

HOST="${MOZIKETO_SSH_HOST:-moziketo}"
REMOTE_ENV="/opt/moziketo/wave.env"

upsert_remote() {
  local key="$1"
  local value="$2"
  ssh "$HOST" "grep -v '^${key}=' '${REMOTE_ENV}' > '${REMOTE_ENV}.tmp' || true; mv '${REMOTE_ENV}.tmp' '${REMOTE_ENV}'"
  ssh "$HOST" "printf '%s=%s\n' '${key}' '${value}' >> '${REMOTE_ENV}'"
}

for key in GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET GITHUB_CLIENT_ID GITHUB_CLIENT_SECRET; do
  val="${!key:-}"
  if [[ -n "$val" ]]; then
    upsert_remote "$key" "$val"
  fi
done

ssh "$HOST" 'cd /opt/moziketo && export MOZ_WAVE_TAG=${MOZ_WAVE_TAG:-oauth-setup} MOZ_WEB_TAG=${MOZ_WEB_TAG:-main} && docker compose up -d wave'
echo "Done. Expect HTTP 302 from: curl -sI https://api.moziketo.ir/api/v1/auth/oauth/google"
