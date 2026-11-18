#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install python dependencies
pip install -r requirements.txt

# Collect static files into staticfiles/
python manage.py collectstatic --no-input

# Apply database migrations
python manage.py migrate

# Seed initial demo data (admin, author, respondent, realistic surveys)
python manage.py seed_demo
