#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

# Install production dependencies
pip install -r requirements.txt

# Collect static files into STATIC_ROOT for Whitenoise
python manage.py collectstatic --noinput

# Apply database migrations
python manage.py migrate
