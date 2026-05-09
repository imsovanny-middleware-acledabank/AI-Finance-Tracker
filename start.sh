#!/usr/bin/env bash
set -o errexit

# Start the web server
gunicorn core.wsgi:application
