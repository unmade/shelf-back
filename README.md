# Shelf App

[![build](https://github.com/unmade/shelf-back/workflows/Test/badge.svg)](https://github.com/unmade/shelf-back/blob/master/.github/workflows/tests.yml)
[![codecov](https://codecov.io/gh/unmade/shelf-back/branch/master/graph/badge.svg)](https://codecov.io/gh/unmade/shelf-back)

This is backend for the Shelf App - a self-hosted file storage.

## Demo

- [https://app.getshelf.cloud/files](https://app.getshelf.cloud/files)
- [https://api.getshelf.cloud/docs](https://api.getshelf.cloud/docs)

## Development

### Running locally

Create a new virtual environment:

```bash
python3 -m venv .venv
source ./.venv/bin/activate && source dev.env
```

Install requirements:

```bash
pip install -r requirements/base.txt requirements/dev.txt requirements/lint.txt requirements/test.txt
```

Install pre-commit hooks:

```bash
pre-commit install
```

Run services:

```bash
docker-compose up -d
```

Apply migration:

```bash
python manage.py migrate schema.esdl
```

Start Celery:

```bash
celery -A app.tasks worker --loglevel=INFO
```

Start the application:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### Running EdgeDB on Apple Silicon

Starting from version 2.0 EdgeDB has native builds for arm64 arch.
The easiest way to run EdgeDB is to install it locally following the
[official docs](https://www.edgedb.com/install).

Unfortunately running edgedb locally doesn't allow to configure port and
certificates, so you have to set `DATABASE_DSN` environment variable to run test:

```bash
DATABASE_DSN=edgedb://edgedb:root@localhost:10700/edgedb  pytest
```

To run a uvicorn you have to unset `DATABASE_DSN` and `DATABASE_TLS_CA_FILE`
environment variables.

### Adding new requirements

This project relies on [pip-tools](https://github.com/jazzband/pip-tools) to manage
requirements.
To add a new one update one of the *.in files in [requirements](requirements) directory,
and then run:

```bash
pip-compile requirements/{updated_file}.in
```

To sync with your env:

```bash
pip-sync requirements/base.txt [requirements/test.txt] ...
```

### Testing

```bash
pytest
```

> Before running tests, make sure EdgeDB instance is up and running. Test runner will
> create a new database and drop it after.

### Building a Docker image

Normally, a docker image is built in CI whenever there is a new tag.

To build a docker image locally:

```bash
docker build . -t shelf_back:0.1.0 --build-arg app_version=0.1.0
```

Optionally, you can provide two environment variables to autocreate a
superuser on the first image run:

- `SHELF_SUPERUSER_USERNAME` - a superuser username
- `SHELF_SUPERUSER_PASSWORD` - a superuser password

## Environment variables

|Name                 | Required | Default | Description|
|:--------------------|:-------- |:------- |:-----------|
|APP_NAME             | - | Shelf  | Application name |
|APP_DEBUG            | - | False  | Whether to run app in debug mode |
|APP_SECRET_KEY       | + | -      | Application secret key. This is used to provide cryptographic signing, and should be set to a unique, unpredictable value |
|APP_VERSION          | - | dev    | Application version. Normally, this env is set during build |
|CACHE_BACKEND_DSN    | - | mem:// | Cache backend DSN. See options [here](https://github.com/Krukov/cashews) |
|CELERY_BACKEND_DSN   | + | -      | Celery broker DSN |
|CELERY_BROKER_DSN    | + | -      | Celery result backend DSN  |
|CLIENT_CACHE_MAX_SIZE| - | -      | Client cache size limit in bytes |
|CORS_ALLOW_ORIGINS   | - | []     | A comma-separated list of origins that should be permitted to make cross-origin requests |
|DATABASE_DSN         | - | -      | Database DSN. If not set, then fallback to EdgeDB envs |
|DATABASE_TLS_CA_FILE | - | -      | Path to TLS Certificate file to connect to the database. If not set, then fallback to EDGEDB_TLS_CA |
|DATABASE_TLS_SECURITY| - | -      | Set the TLS security mode |
|FEATURES_SIGN_UP_DISABLED              | - | False | Whether sign up is disabled or not |
|FEATURES_UPLOAD_FILE_MAX_SIZE_IN_BYTES | - | 104857600 | Maximum upload file size. Default to 100 MB |
|STORAGE_TYPE         | - | filesystem | A primary storage type. Either `filesystem` or `s3` options are available |
|STORAGE_LOCATION     | - | ./data | Storage location. Path should be provided without trailing slash |
|STORAGE_QUOTA_PER_ACCOUNT_IN_BYTES | - | None | Default storage quota per account in bytes. If not set, then account has unlimited storage |
|STORAGE_S3_ACCESS_KEY_ID     | - | -     | S3 access key id. Required only if `s3` storage type is used |
|STORAGE_S3_SECRET_ACCESS_KEY | - | -     | S3 secret access key. Required only if `s3` storage type is used |
|STORAGE_S3_BUCKET_NAME       | - | shelf | S3 bucket to use to store files. Required only if `s3` storage type is used |
|STORAGE_S3_REGION_NAME       | - | -     | S3 region. Required only if `s3` storage type is used |
|SENTRY_DSN                   | - | None   | Sentry DSN |
|SENTRY_ENV                   | - | None   | Sentry environment |
