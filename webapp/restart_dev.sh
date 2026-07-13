#!/bin/bash
# restart_dev.sh — Restart the Flask dev server
#
# WHY THIS SCRIPT EXISTS:
# Flask debug mode spawns a child reloader process. Running `kill %1`
# or just stopping the parent process leaves the child alive, serving
# stale data on port 5001. In one session, 160+ zombie Python processes
# accumulated, causing hours of wrong data being served despite correct
# database values. The user had to manually kill them all.
#
# This script kills ALL Python processes first, waits for the port to
# free up, then starts the server fresh. Always use this script to
# restart the dev server. Never run `kill %1` or `python app.py`
# manually.
#
# ALSO: Python caches WEAPONS, ENEMIES, and SKILLS at import time.
# After ANY database change, you MUST restart the server or the old
# data will keep being served.
#
# Dev server runs on: http://localhost:5001 (debug mode)
# Production uses Gunicorn on port 8001 (see CLAUDE.md Deployment)

cd "$(dirname "$0")"
taskkill //F //IM python.exe 2>/dev/null
sleep 2
python app.py &
