#! /usr/bin/env bash
set -e

# start edgedb-server and export corresponding envs
source start-edgedb

# we use dyno container filesystem as a storage,
# but that storage is not persistent,
# so reindex whenever a container is starting
python manage.py createsuperuser --exist-ok
python manage.py reindex admin
python manage.py reindex-content admin

exec "$@"
