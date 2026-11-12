#!/usr/bin/env bash
# Restore a backup produced by backup.sh into the running compose stack.
# DESTRUCTIVE: replaces the content of the neo_orchestro database. Stop api/worker first.
set -euo pipefail
cd "$(dirname "$0")/.."
file="${1:?usage: scripts/restore.sh backups/neo-<timestamp>.sql.gz}"
test -r "$file" || { echo "cannot read $file" >&2; exit 1; }
read -r -p "This REPLACES the neo_orchestro database with $file. Type 'restore' to continue: " answer
[ "$answer" = "restore" ] || { echo "aborted" >&2; exit 1; }
gunzip -c "$file" | docker compose exec -T db psql -U neo -d neo_orchestro -v ON_ERROR_STOP=1
echo "restored from $file"
