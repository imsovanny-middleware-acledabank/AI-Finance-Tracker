#!/usr/bin/env bash
set -o errexit

# Optional fallback: run Telegram bot in same service when no Render worker exists.
# Enable by setting RUN_BOT_IN_WEB=true in environment.
if [ "${RUN_BOT_IN_WEB:-false}" = "true" ]; then
	if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
		echo "[start.sh] RUN_BOT_IN_WEB=true -> starting Telegram bot in background"
		# Keep default polling unless overridden
		export BOT_MODE="${BOT_MODE:-polling}"
		python manage.py run_bot &
	else
		echo "[start.sh] RUN_BOT_IN_WEB=true but TELEGRAM_BOT_TOKEN is missing; bot not started"
	fi
fi

# Start web server in foreground
gunicorn core.wsgi:application
