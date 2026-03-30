#!/bin/sh
set -e

until flask --app app.py db upgrade; do
    echo "База данных ещё недоступна, повтор через 2 секунды..."
    sleep 2
done

if [ "$FLASK_ENV" = "development" ]; then
    python app.py
else
    exec gunicorn \
        --bind "0.0.0.0:${PORT:-8000}" \
        --workers "${GUNICORN_WORKERS:-2}" \
        --timeout "${GUNICORN_TIMEOUT:-120}" \
        app:app
fi
