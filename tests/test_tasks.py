from app import tasks


def test_celery_works(celery_session_worker):
    task = tasks.ping.delay()
    assert task.get(timeout=3) == "pong"
