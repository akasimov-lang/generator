"""Catch broker-library incompatibility before deployment, without contacting Redis."""
from kombu.transport.redis import Channel
from app.worker import celery_app


def test_redis_transport_can_construct_the_client_class():
    channel = Channel.__new__(Channel)
    client_type = channel._get_client()
    client = client_type(host="127.0.0.1", port=1)
    assert callable(client.ping)
    assert celery_app.tasks["app.worker.dispatch_background_jobs"]
    assert celery_app.tasks["app.worker.background_operation"]
