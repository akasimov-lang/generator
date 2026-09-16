from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4
import pytest
from app import models
from app.generation_recovery import assert_generation_idle, recover_legacy_generation
from test_project_network import env


def test_recovery_preserves_content_and_excludes_recent_or_completed(env):
    db, site, _ = env
    old = datetime.now(timezone.utc) - timedelta(days=25)
    items = []
    for status, date in [("generating", old), ("generation_queued", old),
                         ("generating", datetime.now(timezone.utc)), ("published", old)]:
        item = models.ContentItem(task_id=str(uuid4()), site_id=site.id, topic="Keep",
            slug="keep", generated_json={"text": "Preserve"}, status=status,
            idempotency_key=str(uuid4()), updated_at=date)
        db.add(item); items.append(item)
    db.commit()
    verify = Mock()
    result = recover_legacy_generation(db, [i.id for i in items],
        before=datetime.now(timezone.utc) - timedelta(days=20), verify_idle=verify)
    assert len(result) == 2
    assert verify.call_count == 2
    assert [i.status for i in items] == ["system_stopped", "system_stopped", "generating", "published"]
    assert all(i.generated_json == {"text": "Preserve"} for i in items)
    assert recover_legacy_generation(db, [i.id for i in items],
        before=datetime.now(timezone.utc) - timedelta(days=20), verify_idle=verify) == []


@pytest.mark.parametrize("case", ["missing", "active", "pending", "unacked"])
def test_broker_uncertainty_or_existing_work_blocks_recovery(case):
    app, broker = Mock(), Mock()
    inspect = app.control.inspect.return_value
    inspect.active_queues.return_value = {"worker": [{"name": "generation"}]}
    for name in ("active", "reserved", "scheduled"):
        getattr(inspect, name).return_value = {"worker": []}
    broker.scan_iter.side_effect = lambda **kwargs: iter([b"generation"])
    broker.type.return_value = b"list"
    broker.llen.return_value = 0
    broker.hlen.return_value = 0
    if case == "missing": inspect.reserved.return_value = None
    if case == "active": inspect.active.return_value = {"worker": [{"id": "running"}]}
    if case == "pending": broker.llen.return_value = 1
    if case == "unacked": broker.hlen.return_value = 1
    with pytest.raises(RuntimeError):
        assert_generation_idle(app, broker)
