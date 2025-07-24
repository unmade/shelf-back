FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.2 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

ARG app_version
ENV APP_VERSION=$app_version

ENV HOME_DIR=/usr/src/shelf-back
ENV PYTHONPATH=${HOME_DIR}

WORKDIR ${HOME_DIR}

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    --mount=type=bind,source=.python-version,target=.python-version \
    uv sync --locked --no-default-groups

ENV PATH="${HOME_DIR}/.venv/bin:$PATH"

COPY ./docker-entrypoint.sh ${HOME_DIR}/docker-entrypoint.sh
RUN chmod +x ${HOME_DIR}/docker-entrypoint.sh

COPY ./dbschema ./gunicorn_conf.py ./LICENSE ./manage.py ${HOME_DIR}/

COPY ./app ${HOME_DIR}/app

EXPOSE 80

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-c", "gunicorn_conf.py", "app.api.main:app"]
