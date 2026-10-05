#!/usr/bin/env bash
# Build script for Vercel deployment
# This script runs during the Vercel build process

set -e  # Exit on error

if [ "${VERCEL:-}" = "1" ] && [ -z "${DATABASE_URL:-}" ]; then
  echo "ERROR: DATABASE_URL is required for Vercel deployments. Configure a PostgreSQL database in Vercel Project Settings." >&2
  exit 1
fi

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

if [ "${VERCEL:-}" = "1" ]; then
  echo "Applying database migrations..."
  python manage.py migrate --noinput
fi

echo "Build completed successfully!"
