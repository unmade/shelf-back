FROM python:3.10-slim

COPY ./requirements/base.txt /requirements/

RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements/base.txt

# uncomment this to build on arm64
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements/base.txt \
    && apt-get purge -y --auto-remove gcc libc-dev

ARG app_version
ENV APP_VERSION=$app_version

ENV HOME_DIR /usr/src/shelf-back
ENV PYTHONPATH=${HOME_DIR}

COPY ./start.sh ${HOME_DIR}/start.sh
RUN chmod +x ${HOME_DIR}/start.sh

COPY ./gunicorn_conf.py ${HOME_DIR}/gunicorn_conf.py

COPY ./app ${HOME_DIR}/app
WORKDIR ${HOME_DIR}

EXPOSE 80

CMD ["./start.sh"]
