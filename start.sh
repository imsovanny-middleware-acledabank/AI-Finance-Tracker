#!/usr/bin/env bash
set -o errexit

# Start the Telegram bot in the background
python manage.py run_bot &

# Start the web server
gunicorn core.wsgi:application
