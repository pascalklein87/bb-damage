#!/usr/bin/env bash
# bb-damage production deploy. Runs ON the VPS (damage.bloodngold.com).
#   ssh root@46.225.141.38 "bash /var/www/bb-damage/deploy.sh"
# Pulls the repo + bb-damage-engine, reinstalls deps, restarts gunicorn on 8002, verifies 200.
set -euo pipefail

APP=/var/www/bb-damage
VENV=$APP/venv
PORT=8002

echo "[1/5] pull"
git -C "$APP" pull --ff-only
git -C /var/www/bb-damage-engine pull --ff-only || true

echo "[2/5] deps"
"$VENV/bin/pip" install -q -r "$APP/webapp/requirements.txt"
# pip skips an already-installed git dependency while its version stays 0.1.0,
# so new bb-damage-engine commits never land without a forced reinstall (2026-07-13 outage).
"$VENV/bin/pip" install -q --force-reinstall --no-deps \
  "bb-damage-engine @ git+ssh://git@github.com/pascalklein87/bb-damage-engine.git@main#subdirectory=package"

echo "[3/5] stop old gunicorn on $PORT"
fuser -k ${PORT}/tcp 2>/dev/null || true
sleep 1

echo "[4/5] start gunicorn on $PORT"
"$VENV/bin/gunicorn" --chdir "$APP/webapp" --workers 3 \
  --bind 127.0.0.1:${PORT} "app:create_app()" --daemon \
  --error-logfile /var/log/gunicorn-damage-error.log

echo "[5/5] verify"
sleep 2
code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:${PORT}/)
echo "  / -> $code"
[ "$code" = "200" ] || { echo "DEPLOY FAILED: / not 200"; exit 1; }
echo "OK: bb-damage live on 127.0.0.1:${PORT} (nginx -> damage.bloodngold.com)"
