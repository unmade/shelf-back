#! /usr/bin/env bash
set -e

# start edgedb-server and export corresponding envs
source start-edgedb

exec "$@"
