"""Prefork workers must not retain idle DB connections between long AI tasks."""
from celery.signals import task_postrun, worker_process_init


@worker_process_init.connect
def reset_inherited_pool(**_):
    from app.db import engine
    if engine.dialect.name == 'postgresql':
        engine.dispose(close=False)


@task_postrun.connect
def release_idle_pool(**_):
    from app.db import engine
    if engine.dialect.name == 'postgresql':
        # Task sessions and advisory-lock contexts have exited. dispose closes
        # checked-in connections only; no other process/active transaction is touched.
        engine.dispose()
