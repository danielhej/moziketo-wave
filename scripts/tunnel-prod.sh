#!/usr/bin/env bash
# SSH tunnel to production PostgreSQL + Redis (bound to 127.0.0.1 on moziketo-hand).
#
# Usage:
#   ./scripts/tunnel-prod.sh
#
# Then connect locally:
#   PostgreSQL — localhost:15432 (user/db from /opt/moziketo/wave.env on server)
#   Redis      — localhost:16379
#
# DataGrip: General host=127.0.0.1 port=5432 + SSH tab (host=moziketo, user=deploy)
#           OR host=localhost port=15432 with this tunnel running (no SSH tab).

set -euo pipefail

SSH_HOST="${MOZIKETO_SSH_HOST:-moziketo}"
LOCAL_PG_PORT="${LOCAL_PG_PORT:-15432}"
LOCAL_REDIS_PORT="${LOCAL_REDIS_PORT:-16379}"

echo "→ PostgreSQL  localhost:${LOCAL_PG_PORT}  →  ${SSH_HOST}:127.0.0.1:5432"
echo "→ Redis       localhost:${LOCAL_REDIS_PORT}  →  ${SSH_HOST}:127.0.0.1:6379"
echo "  Ctrl+C to close"
echo

exec ssh -N \
  -o ExitOnForwardFailure=yes \
  -L "${LOCAL_PG_PORT}:127.0.0.1:5432" \
  -L "${LOCAL_REDIS_PORT}:127.0.0.1:6379" \
  "${SSH_HOST}"
