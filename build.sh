#!/usr/bin/env bash
# Exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Auto-create superuser from environment variables (if set)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
	python manage.py createsuperuser \
		--noinput \
		--username "$DJANGO_SUPERUSER_USERNAME" \
		--email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" \
		2>/dev/null || echo "Superuser already exists, skipping."
fi
