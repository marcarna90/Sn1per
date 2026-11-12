#!/usr/bin/env bash
# End-to-end smoke test with REAL processes: fake DNS server, API (uvicorn), Celery worker,
# nginx serving the built frontend and proxying the API, PostgreSQL and Redis.
# Docker is not required. See e2e/README.md.
set -euo pipefail

E2E_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$E2E_DIR")"

: "${NEO_E2E_DATABASE_URL:?an EMPTY PostgreSQL database, e.g. postgresql+pg8000://neo:...@127.0.0.1:5432/neo_e2e}"
: "${NEO_E2E_REDIS_URL:?a Redis URL dedicated to this run, e.g. redis://127.0.0.1:6379/14}"
export E2E_VENV="${E2E_VENV:-$ROOT/backend/.venv}"
export E2E_WEB_PORT="${E2E_WEB_PORT:-8080}"
export E2E_API_PORT="${E2E_API_PORT:-8000}"
export E2E_DNS_ADDRESS="${E2E_DNS_ADDRESS:-127.0.0.77}"
export E2E_WORKDIR="${E2E_WORKDIR:-$(mktemp -d)}"
mkdir -p "$E2E_WORKDIR"

export PYTHONPATH="$ROOT/backend/src"
export NEO_SECRET_KEY
NEO_SECRET_KEY="$("$E2E_VENV/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
export NEO_DATABASE_URL="$NEO_E2E_DATABASE_URL"
export NEO_REDIS_URL="$NEO_E2E_REDIS_URL"
export NEO_ENV=development NEO_COOKIE_SECURE=false NEO_LOG_JSON=true
export NEO_DNS_NAMESERVERS="$E2E_DNS_ADDRESS"
export E2E_PASSWORD
E2E_PASSWORD="$("$E2E_VENV/bin/python" -c 'import secrets; print(secrets.token_urlsafe(18))')"
export E2E_BASE_URL="http://127.0.0.1:$E2E_WEB_PORT" E2E_API_URL="http://127.0.0.1:$E2E_API_PORT"
export E2E_RECORDS="$E2E_WORKDIR/records.json" E2E_DNS_LOG="$E2E_WORKDIR/dns.log"
export E2E_WORKER_CTL="$E2E_DIR/worker_ctl.sh"
export E2E_UI_ADMIN_EMAIL="ui-admin@example.org" E2E_API_ADMIN_EMAIL="api-admin@example.org"
export E2E_OTHER_ADMIN_EMAIL="other-admin@example.org"
export E2E_SHOTS="${E2E_SHOTS:-$E2E_WORKDIR/screenshots}"

pids=()
cleanup() {
  status=$?
  "$E2E_WORKER_CTL" stop 2>/dev/null || true
  for pid in "${pids[@]:-}"; do [ -n "$pid" ] && kill "$pid" 2>/dev/null || true; done
  if [ "$status" -ne 0 ]; then
    echo "---- run failed (exit $status); log tails in $E2E_WORKDIR ----" >&2
    for f in api.log worker.log nginx-error.log dns.log; do
      [ -f "$E2E_WORKDIR/$f" ] && { echo "== $f"; tail -n 15 "$E2E_WORKDIR/$f"; } >&2
    done
  fi
}
trap cleanup EXIT

wait_for() { # url, seconds
  for _ in $(seq 1 "$2"); do curl -fsS -o /dev/null "$1" 2>/dev/null && return 0; sleep 1; done
  echo "timeout waiting for $1" >&2; return 1
}

echo "== workdir: $E2E_WORKDIR"
[ -f "$ROOT/frontend/dist/index.html" ] || (cd "$ROOT/frontend" && npm ci --ignore-scripts && npm run build)

# DNS records served to the stack. Public-looking addresses: the engines only ever *query* DNS,
# nothing connects to them.
cat >"$E2E_RECORDS" <<JSON
{
  "www.lab.test": {"A": ["93.184.216.34"], "TXT": ["e2e: no spf here"], "MX": ["10 mail.lab.test."]},
  "ui.lab.test":  {"A": ["93.184.216.35"], "TXT": ["v=spf1 -all"]}
}
JSON
"$E2E_VENV/bin/python" "$E2E_DIR/fake_dns.py" "$E2E_RECORDS" "$E2E_DNS_ADDRESS" 53 >"$E2E_DNS_LOG" 2>&1 &
pids+=($!)
sleep 1
"$E2E_VENV/bin/python" - <<PY
import dns.resolver
r = dns.resolver.Resolver(configure=False); r.nameservers = ["$E2E_DNS_ADDRESS"]
print("fake DNS answers www.lab.test A =", r.resolve("www.lab.test.", "A")[0])
PY
: >"$E2E_DNS_LOG" # forget the probe query

echo "== alembic upgrade head"
(cd "$ROOT/backend" && "$E2E_VENV/bin/alembic" upgrade head 2>&1 | tail -n 2)

echo "== bootstrap organisations through the CLI (password via stdin)"
for spec in "UI lab:e2e-ui:$E2E_UI_ADMIN_EMAIL" "API lab:e2e-api:$E2E_API_ADMIN_EMAIL" \
            "Other org:e2e-other:$E2E_OTHER_ADMIN_EMAIL"; do
  IFS=: read -r name slug email <<<"$spec"
  printf '%s\n' "$E2E_PASSWORD" | "$E2E_VENV/bin/python" -m neo_orchestro.cli create-org \
    --name "$name" --slug "$slug" --admin-email "$email" --password-stdin | tail -n 1
done

echo "== start API"
"$E2E_VENV/bin/uvicorn" neo_orchestro.api.app:create_app --factory --host 127.0.0.1 \
  --port "$E2E_API_PORT" --proxy-headers >"$E2E_WORKDIR/api.log" 2>&1 &
pids+=($!)
wait_for "$E2E_API_URL/health/ready" 60

echo "== start nginx (the real frontend/nginx/default.conf, only paths adapted)"
sed -e "s|listen 8080;|listen 127.0.0.1:$E2E_WEB_PORT;|" \
    -e "s|/usr/share/nginx/html|$ROOT/frontend/dist|" \
    -e "s|/etc/nginx/snippets/|$ROOT/frontend/nginx/|" \
    -e "s|http://api:8000|$E2E_API_URL|" \
    "$ROOT/frontend/nginx/default.conf" >"$E2E_WORKDIR/default.conf"
mkdir -p "$E2E_WORKDIR/nginx-tmp"
cat >"$E2E_WORKDIR/nginx.conf" <<CONF
pid $E2E_WORKDIR/nginx.pid;
error_log $E2E_WORKDIR/nginx-error.log;
events {}
http {
  include /etc/nginx/mime.types;
  access_log $E2E_WORKDIR/nginx-access.log;
  client_body_temp_path $E2E_WORKDIR/nginx-tmp/body;
  proxy_temp_path $E2E_WORKDIR/nginx-tmp/proxy;
  fastcgi_temp_path $E2E_WORKDIR/nginx-tmp/fcgi;
  uwsgi_temp_path $E2E_WORKDIR/nginx-tmp/uwsgi;
  scgi_temp_path $E2E_WORKDIR/nginx-tmp/scgi;
  include $E2E_WORKDIR/default.conf;
}
CONF
nginx -t -c "$E2E_WORKDIR/nginx.conf" -e "$E2E_WORKDIR/nginx-error.log"
nginx -c "$E2E_WORKDIR/nginx.conf" -e "$E2E_WORKDIR/nginx-error.log" -g 'daemon off;' &
pids+=($!)
wait_for "$E2E_BASE_URL/healthz" 15

echo "== start Celery worker"
"$E2E_WORKER_CTL" start

failed=0
if [ "${E2E_SKIP_BROWSER:-0}" != "1" ]; then
  echo; echo "================ browser smoke (Playwright / Chromium) ================"
  node "$E2E_DIR/browser_smoke.cjs" || failed=1
fi
echo; echo "================ API smoke (real HTTP through nginx) ================"
"$E2E_VENV/bin/python" -I "$E2E_DIR/smoke.py" || failed=1

echo; echo "== logs and screenshots: $E2E_WORKDIR"
exit "$failed"
