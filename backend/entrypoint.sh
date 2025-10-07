#!/bin/sh
set -e
python manage.py migrate --noinput
python manage.py reset_connections
exec daphne -b 0.0.0.0 -p 8000 config.asgi:application
