#!/bin/bash
# Build script for Vercel deployment

set -e

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Running migrations..."
python manage.py migrate --noinput 2>/dev/null || echo "Warning: Migrations skipped (may be expected on first run)"

echo "Build completed successfully!"
