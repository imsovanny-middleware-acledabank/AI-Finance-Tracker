#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "[build] installing python dependencies..."
python -m pip install --no-cache-dir --disable-pip-version-check -r requirements.txt
echo "[build] python dependencies installed."

BUILD_FRONTEND="${BUILD_FRONTEND:-true}"
RUN_COLLECTSTATIC="${RUN_COLLECTSTATIC:-true}"
RUN_MIGRATE="${RUN_MIGRATE:-false}"
RUN_BOT_DURING_BUILD="${RUN_BOT_DURING_BUILD:-false}"

# Build frontend SPA and stage built assets for Django static/template serving
if [ "$BUILD_FRONTEND" = "true" ] && [ -f "frontend/package.json" ]; then
	if command -v npm >/dev/null 2>&1; then
		echo "[build] npm detected, building frontend..."
		cd frontend
		if [ -f "package-lock.json" ]; then
			npm ci
		else
			npm install
		fi
		npm run build
		cd ..

		mkdir -p tracker/templates/spa
		mkdir -p tracker/static/spa/assets
		cp frontend/dist/index.html tracker/templates/spa/index.html
		if [ -d "frontend/dist/assets" ]; then
			rm -rf tracker/static/spa/assets/*
			cp -R frontend/dist/assets/. tracker/static/spa/assets/
		fi
	else
		echo "[build] npm not found, skipping frontend build and using committed SPA assets."
	fi
fi

# Fail fast only when both source SPA and staged SPA are missing.
if [ "$BUILD_FRONTEND" = "true" ] && [ ! -f "tracker/templates/spa/index.html" ]; then
	echo "[build] ERROR: tracker/templates/spa/index.html not found."
	echo "[build] Please commit staged SPA assets or ensure npm is available during build."
	exit 1
fi

if [ "$RUN_COLLECTSTATIC" = "true" ]; then
	python manage.py collectstatic --no-input
fi

if [ "$RUN_MIGRATE" = "true" ]; then
	echo "[build] RUN_MIGRATE=true -> running migrations in build phase"
	python manage.py migrate

	# Auto-create/update superuser from environment variables (if set)
	if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
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

print("Admin user created" if created else "Admin user updated")
PY
	fi
else
	echo "[build] RUN_MIGRATE=false -> skipping DB tasks (migrate/superuser) in build phase"
fi

# Optional: start Telegram bot during build (NOT recommended for production builds).
# Default is false to avoid blocking or unstable build behavior.
if [ "$RUN_BOT_DURING_BUILD" = "true" ]; then
	if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
		echo "[build] RUN_BOT_DURING_BUILD=true -> starting Telegram bot in background"
		python manage.py run_bot &
	else
		echo "[build] RUN_BOT_DURING_BUILD=true but TELEGRAM_BOT_TOKEN is missing; bot not started"
	fi
fi
