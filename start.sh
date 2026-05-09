#!/usr/bin/env bash
set -o errexit

# Optional fallback: run Telegram bot in same service when no Render worker exists.
# Enable by setting RUN_BOT_IN_WEB=true in environment.

# Run DB migrations at runtime (recommended on Render).
if [ "${RUN_MIGRATE_ON_START:-true}" = "true" ]; then
	echo "[start.sh] RUN_MIGRATE_ON_START=true -> running migrations"
	if ! python manage.py migrate --noinput; then
		echo "[start.sh] WARNING: migrate failed at startup"
		echo "[start.sh] Hint: verify DATABASE_URL, database region/network, and private host accessibility"
		echo "[start.sh] Hint: if using Render private DB host, web service must be in same region/private network"
		if [ "${MIGRATE_STRICT:-false}" = "true" ]; then
			echo "[start.sh] MIGRATE_STRICT=true -> exiting due to migration failure"
			exit 1
		fi
		echo "[start.sh] MIGRATE_STRICT=false -> continuing startup without blocking web process"
	fi
else
	echo "[start.sh] RUN_MIGRATE_ON_START=false -> skipping migrations"
fi

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
