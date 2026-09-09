#!/usr/bin/env bash
# Build script for Vercel deployment
# This script runs during the Vercel build process

set -e  # Exit on error

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --noinput --clear

echo "Build completed successfully!"