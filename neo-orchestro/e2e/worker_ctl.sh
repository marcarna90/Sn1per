#!/usr/bin/env bash
# Start / stop the Celery worker of the e2e run (used by run.sh and by smoke.py).
# Needs: E2E_WORKDIR, E2E_VENV, PYTHONPATH and the NEO_* environment.
set -euo pipefail

pidfile="$E2E_WORKDIR/worker.pid"
app="neo_orchestro.orchestrator.worker:app"

case "${1:-}" in
  start)
    setsid "$E2E_VENV/bin/celery" -A "$app" worker -Q scans --concurrency=2 --loglevel=INFO \
      >>"$E2E_WORKDIR/worker.log" 2>&1 &
    echo $! >"$pidfile"
    for _ in $(seq 1 60); do
      if "$E2E_VENV/bin/celery" -A "$app" inspect ping --timeout 2 >/dev/null 2>&1; then
        exit 0
      fi
      sleep 1
    done
    echo "worker did not answer ping within 60 s" >&2
    exit 1
    ;;
  stop)
    [ -f "$pidfile" ] || exit 0
    pid="$(cat "$pidfile")"
    kill -TERM -- "-$pid" 2>/dev/null || true # the worker leads its own process group
    for _ in $(seq 1 60); do
      kill -0 "$pid" 2>/dev/null || { rm -f "$pidfile"; exit 0; }
      sleep 0.5
    done
    kill -KILL -- "-$pid" 2>/dev/null || true
    rm -f "$pidfile"
    ;;
  *)
    echo "usage: $0 start|stop" >&2
    exit 2
    ;;
esac
