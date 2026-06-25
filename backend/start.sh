#!/bin/bash

# Start Celery worker in the background
celery -A app.core.celery_app worker -Q notifications,analytics --loglevel=info &

# Start Celery beat in the background
celery -A app.core.celery_app beat --loglevel=info &

# Start Uvicorn in the foreground (keeps the container running)
uvicorn app.main:app --host 0.0.0.0 --port 8000
