"""Bound idle connections without replacing a pool shared by worker threads."""
import os
from celery.signals import task_postrun, worker_process_init


@worker_process_init.connect
def reset_inherited_pool(**_):
    from app.db import engine
    if engine.dialect.name == 'postgresql':
        engine.dispose(close=False)


@task_postrun.connect
def release_idle_pool(**_):
    # Planning threads share one bounded engine pool. Replacing it after each
    # task would detach connections still checked out by the other 29 tasks.
    if os.environ.get('WORKER_SHARED_DB_POOL') == '1':
        return
    from app.db import engine
    if engine.dialect.name == 'postgresql':
        # Task sessions and advisory-lock contexts have exited. dispose closes
        # checked-in connections only; no other process/active transaction is touched.
        engine.dispose()
