# Shelf App

[![build](https://github.com/unmade/shelf-back/workflows/Test/badge.svg)](https://github.com/unmade/shelf-back/blob/master/.github/workflows/tests.yml)
[![codecov](https://codecov.io/gh/unmade/shelf-back/branch/master/graph/badge.svg)](https://codecov.io/gh/unmade/shelf-back)

This is backend for the Shelf App - a self-hosted file storage.

## Demo

- [https://app.getshelf.cloud/files](https://app.getshelf.cloud/files)
- [https://api.getshelf.cloud/docs](https://api.getshelf.cloud/docs)

## Development

### Running locally

This project relies on [uv](https://docs.astral.sh/uv/) to manage
requirements.

Install requirements:

```bash
uv sync --locked --all-groups
```

Install pre-commit hooks:

```bash
pre-commit install
```

Run services:

```bash
docker-compose up -d
```

Start the worker:

```bash
uv run arq app.worker.main.WorkerSettings
```

Start the application:

```bash
uv run uvicorn app.api.main:app --host 0.0.0.0 --port 8000
```

### Testing

```bash
pytest
```

> Test runner will create a new test database.

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
|DATABASE__DSN                 | + | -      | Database DSN |
|FEATURES__MAX_FILE_SIZE_TO_THUMBNAIL | - | 20MB | Thumbnails won't be generated for files larger than specified size. |
|FEATURES__MAX_IMAGE_PIXELS | - | 89_478_485 | Don't process images if the number of pixels in an image is over limit. |
|FEATURES__PHOTOS_LIBRARY_PATH | - | Photos/Library | All media files within that path will appear in the Photos. |
|FEATURES__PRE_GENERATED_THUMBNAIL_SIZES | - | [72, 768, 2880] | Thumbnail sizes that are automatically generated on file upload. |
|FEATURES__SIGN_UP_ENABLED     | - | True   | Whether sign up is enabled or not |
|FEATURES__SHARED_LINKS_ENABLED | - | True  | Whether via link enabled. Note, this setting doesn't affect superusers. |
|FEATURES__UPLOAD_FILE_MAX     | - | 100MB  | Maximum upload file size. Default to 100 MB |
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
|STORAGES__DEFAULT__TYPE       | - | filesystem | A primary storage type. Either `filesystem` or `s3` options are available |
|STORAGES__DEFAULT__FS_LOCATION          | - | ./data | FileSystem Storage location. Path should be provided without trailing slash |
|STORAGES__DEFAULT__S3_LOCATION          | + | -      | S3 location |
|STORAGES__DEFAULT__S3_ACCESS_KEY_ID     | - | -      | S3 access key id. Required only if `s3` storage type is used |
|STORAGES__DEFAULT__S3_SECRET_ACCESS_KEY | - | -      | S3 secret access key. Required only if `s3` storage type is used |
|STORAGES__DEFAULT__S3_BUCKET_NAME       | - | shelf  | S3 bucket to use to store files. Required only if `s3` storage type is used |
|STORAGES__DEFAULT__S3_REGION_NAME       | - | -      | S3 region. Required only if `s3` storage type is used |
|STORAGES__MEDIA__TYPE         | - | filesystem | A "media" storage type to store thumbnails, avatars, etc. Either `filesystem` or `s3` options are available. |
|STORAGES__MEDIA__FS_LOCATION          | - | ./data | FileSystem Storage location. Path should be provided without trailing slash |
|STORAGES__MEDIA__S3_LOCATION          | - | -      | S3 location |
|STORAGES__MEDIA__S3_ACCESS_KEY_ID     | - | -      | S3 access key id. Required only if `s3` storage type is used |
|STORAGES__MEDIA__S3_SECRET_ACCESS_KEY | - | -      | S3 secret access key. Required only if `s3` storage type is used |
|STORAGES__MEDIA__S3_BUCKET_NAME       | - | shelf  | S3 bucket to use to store files. Required only if `s3` storage type is used |
|STORAGES__MEDIA__S3_REGION_NAME       | - | -      | S3 region. Required only if `s3` storage type is used |
|WORKER__BROKER_DSN            | + | -      | Worker broker DSN |
