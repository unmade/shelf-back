#! /usr/bin/env sh
set -e

gunicorn -k uvicorn.workers.UvicornWorker -c gunicorn_conf.py app.main:app
