#! /usr/bin/env bash
set -e

python manage.py migrate ./dbschema/default.esdl

if [[ -n "${SHELF_SUPERUSER_USERNAME}" && -n "${SHELF_SUPERUSER_PASSWORD}" ]]; then
    if [ ! -d "${STORAGE_LOCATION}/${SHELF_SUPERUSER_USERNAME}" ]; then
        python manage.py createsuperuser
    fi
fi

exec "$@"
