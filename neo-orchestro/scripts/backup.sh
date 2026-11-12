#!/usr/bin/env bash
# Logical PostgreSQL backup of the running compose stack. Writes backups/neo-<UTC>.sql.gz (0600).
# The audit log is part of the dump: keep backups as protected as the database itself.
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
mkdir -p backups
out="backups/neo-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
docker compose exec -T db pg_dump -U neo -d neo_orchestro --no-owner --clean --if-exists | gzip -9 > "$out"
test -s "$out" || { echo "backup is empty, removing" >&2; rm -f "$out"; exit 1; }
echo "wrote $out"
