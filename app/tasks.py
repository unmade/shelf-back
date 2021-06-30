from celery import Celery

from app import config

celery_app = Celery(
    __name__,
    backend='rpc',
    broker=config.CELERY_BROKER_DSN,
)


@celery_app.task
def ping() -> str:
    return "pong"
