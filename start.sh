#!/usr/bin/env bash
set -o errexit

# Optional fallback: run Telegram bot in same service when no Render worker exists.
# Default is enabled so ./start.sh can auto-run bot unless explicitly disabled.

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

# Auto-create/update superuser at runtime (Render-friendly)
# Requires DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD.
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
	echo "[start.sh] ensuring Django superuser exists"
	python manage.py shell <<'PY'
from django.contrib.auth import get_user_model
import os

User = get_user_model()
username = os.environ["DJANGO_SUPERUSER_USERNAME"]
password = os.environ["DJANGO_SUPERUSER_PASSWORD"]
email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "admin@example.com")

user, created = User.objects.get_or_create(username=username, defaults={"email": email})
user.email = email
user.is_staff = True
user.is_superuser = True
user.is_active = True
user.set_password(password)
user.save()

print("[start.sh] superuser created" if created else "[start.sh] superuser updated")
PY
else
	echo "[start.sh] DJANGO_SUPERUSER_USERNAME/PASSWORD not set -> skipping superuser ensure"
fi

RUN_BOT_IN_WEB_EFFECTIVE="${RUN_BOT_IN_WEB:-true}"
echo "[start.sh] RUN_BOT_IN_WEB=${RUN_BOT_IN_WEB_EFFECTIVE} | BOT_MODE=${BOT_MODE:-polling}"

if [ "${RUN_BOT_IN_WEB_EFFECTIVE}" = "true" ]; then
	if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
		echo "[start.sh] RUN_BOT_IN_WEB=true -> starting Telegram bot in background"
		# Keep default polling unless overridden
		export BOT_MODE="${BOT_MODE:-polling}"
		python manage.py run_bot &
	else
		echo "[start.sh] RUN_BOT_IN_WEB=true but TELEGRAM_BOT_TOKEN is missing; bot not started"
	fi
else
	echo "[start.sh] RUN_BOT_IN_WEB=false -> skipping bot startup in web service"
fi

# Start web server in foreground
gunicorn core.wsgi:application
