#! /usr/bin/env bash
set -e

python manage.py migrate

if [[ -n "${SHELF_SUPERUSER_USERNAME}" && -n "${SHELF_SUPERUSER_PASSWORD}" ]]; then
    if [ ! -d "${STORAGE__LOCATION}/${SHELF_SUPERUSER_USERNAME}" ]; then
        python manage.py createsuperuser --exist-ok
    fi
fi

exec "$@"
