# Shelf

[![build](https://github.com/unmade/shelf-back/workflows/Test/badge.svg)](https://github.com/unmade/shelf-back/blob/master/.github/workflows/tests.yml)
[![codecov](https://codecov.io/gh/unmade/shelf-back/branch/master/graph/badge.svg)](https://codecov.io/gh/unmade/shelf-back)

This is backend application for the Shelf project (in-progress).

## Development

### Running locally

Create a new virtual environment:

```bash
python3 -m venv .venv
source ./.venv/bin/activate && source .env
```

Install requirements:

```bash
pip install -r requirements/base.txt requirements/dev.txt requirements/lint.txt requirements/test.txt
```

Install pre-commit hooks:

```bash
pre-commit install
```

Run EdgeDB:

```bash
docker-compose up -d
```

Apply migration:

```bash
python manage.py migrate schema.esdl
```

Sync media types:

```bash
python manage.py syncmediatypes
```

Start the application:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
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
pip-sync requirements/base.txt [requirements/test.txt]
```

### Testing

```bash
pytest
```

> Before running tests, make sure EdgeDB instance is up and running. Test runner will
> create a new database and drop it after.
