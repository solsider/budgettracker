#!/bin/sh
set -e

until flask --app app.py db upgrade; do
    echo "База данных ещё недоступна, повтор через 2 секунды..."
    sleep 2
done

python app.py
