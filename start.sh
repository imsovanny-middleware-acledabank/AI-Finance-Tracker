#!/usr/bin/env bash
set -o errexit

# IMPORTANT:
# Do not start Telegram bot in web service by default.
# Bot should run in dedicated worker service to avoid getUpdates conflicts.
if [ "${START_BOT_IN_WEB:-false}" = "true" ]; then
  echo "[start] START_BOT_IN_WEB=true -> starting bot in web dyno (not recommended in production)"
  python manage.py run_bot &
fi

# Start the web server
gunicorn core.wsgi:application
