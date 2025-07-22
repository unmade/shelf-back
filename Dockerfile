FROM python:3.12-slim

COPY ./requirements/base.txt /requirements/

RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements/base.txt

ARG app_version
ENV APP_VERSION=$app_version

ENV HOME_DIR /usr/src/shelf-back
ENV PYTHONPATH=${HOME_DIR}

COPY ./docker-entrypoint.sh ${HOME_DIR}/docker-entrypoint.sh
RUN chmod +x ${HOME_DIR}/docker-entrypoint.sh

COPY ./dbschema ${HOME_DIR}/dbschema
COPY ./gunicorn_conf.py ${HOME_DIR}/gunicorn_conf.py
COPY ./LICENSE ${HOME_DIR}}/LICENSE
COPY ./manage.py ${HOME_DIR}/manage.py

COPY ./app ${HOME_DIR}/app
WORKDIR ${HOME_DIR}

EXPOSE 80

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-c", "gunicorn_conf.py", "app.api.main:app"]
