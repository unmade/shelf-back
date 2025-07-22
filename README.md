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
source ./.venv/bin/activate
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

Start the worker:

```bash
arq app.worker.main.WorkerSettings
```

Start the application:

```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

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

> Before running tests, make sure Gel (EdgeDB) instance is up and running.
> Test runner will create a new database and drop it after.

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

|Name                          | Required | Default | Description|
|:-----------------------------|:-------- |:------- |:-----------|
|APP_NAME                      | - | Shelf  | Application name |
|APP_DEBUG                     | - | False  | Whether to run app in debug mode |
|APP_VERSION                   | - | dev    | Application version. Normally, this env is set during build |
|AUTH__ACCESS_TOKEN_TTL        | - | 15m    | A time-to-live of the access token. |
|AUTH__SECRET_KEY              | + | -      | Application secret key. This is used to provide cryptographic signing, and should be set to a unique, unpredictable value |
|AUTH__SERVICE_TOKEN           | - | None   | A service token that is used to authorize external services in internal API. |
|AUTH__REFRESH_TOKEN_TTL       | - | 3d     | A time-to-live of the refresh token. |
|CACHE__BACKEND_DSN            | - | mem:// | Cache backend DSN. See [options](https://github.com/Krukov/cashews) |
|CACHE__DISK_CACHE_MAX_SIZE    | - | -      | Client cache size limit in bytes. Can be set in a format like "512MB", "1GB" |
|CORS__ALLOWED_ORIGINS         | - | []     | A comma-separated list of origins that should be permitted to make cross-origin requests |
|DATABASE__DSN                 | - | -      | Database DSN. If not set, then fallback to Gel envs |
|DATABASE__GEL_TLS_CA_FILE  | - | -      | Path to TLS Certificate file to connect to the database. If not set, then fallback to GEL_TLS_CA |
|DATABASE__GEL_TLS_SECURITY | - | -      | Set the TLS security mode |
|FEATURES__MAX_FILE_SIZE_TO_THUMBNAIL | - | 20MB | Thumbnails won't be generated for files larger than specified size. |
|FEATURES__MAX_IMAGE_PIXELS | - | 89_478_485 | Don't process images if the number of pixels in an image is over limit. |
|FEATURES__PHOTOS_LIBRARY_PATH | - | Photos/Library | All media files within that path will appear in the Photos. |
|FEATURES__PRE_GENERATED_THUMBNAIL_SIZES | - | [72, 768, 2880] | Thumbnail sizes that are automatically generated on file upload. |
|FEATURES__SIGN_UP_DISABLED    | - | False  | Whether sign up is disabled or not |
|FEATURES__SHARED_LINKS_DISABLED | - | False  | Whether via link disabled. Note, this setting doesn't affect superusers. |
|FEATURES__UPLOAD_FILE_MAX     | - | 100MB | Maximum upload file size. Default to 100 MB |
|FEATURES__VERIFICATION_REQUIRED | - | False | Whether user account has to be verified to upload files. |
|INDEXER__URL                  | - | None   | A URL to the Indexer service. If not specified, the file won't be indexed. |
|INDEXER__TIMEOUT              | - | 10     | A timeout to wait response from indexer. |
|MAIL__TYPE                    | - | smtp   | Backend to use for sending emails. |
|MAIL__SENDER                  | - | <no-reply@getshelf.cloud>  | Email sender on behalf of application. |
|MAIL__SMTP_HOSTNAME           | - | localhost  | SMTP hostname. |
|MAIL__SMTP_PORT               | - | 1025   | SMTP port. |
|MAIL__SMTP_USERNAME           | - | None   | SMTP username. |
|MAIL__SMTP_PASSWORD           | - | None   | SMTP password. |
|MAIL__SMTP_USE_TLS            | - | false  | Whether to use TLS connection to SMTP server. |
|SENTRY__DSN                   | - | None   | Sentry DSN |
|SENTRY__ENV                   | - | None   | Sentry environment |
|STORAGE__TYPE                 | - | filesystem | A primary storage type. Either `filesystem` or `s3` options are available |
|STORAGE__QUOTA                | - | None   | Default storage quota per account in bytes. If not set, then account has unlimited storage. Can be set in a format like "512MB", "1GB"  |
|STORAGE__FS_LOCATION          | - | ./data | FileSystem Storage location. Path should be provided without trailing slash |
|STORAGE__S3_LOCATION          | + | -      | S3 location |
|STORAGE__S3_ACCESS_KEY_ID     | - | -      | S3 access key id. Required only if `s3` storage type is used |
|STORAGE__S3_SECRET_ACCESS_KEY | - | -      | S3 secret access key. Required only if `s3` storage type is used |
|STORAGE__S3_BUCKET_NAME       | - | shelf  | S3 bucket to use to store files. Required only if `s3` storage type is used |
|STORAGE__S3_REGION_NAME       | - | -      | S3 region. Required only if `s3` storage type is used |
|WORKER__BROKER_DSN            | + | -      | Worker broker DSN |
