from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.api import delete_duplicate_sites
from app.db import Base


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    return Session(engine)


def test_delete_duplicate_sites_removes_only_unlinked_local_projects() -> None:
    with make_session() as db:
        removable = models.Site(
            name="duplicate-free",
            base_url="https://duplicate-free.test",
            publication_endpoint="https://duplicate-free.test/api/content",
            project_status="duplicate",
        )
        linked = models.Site(
            name="duplicate-linked",
            base_url="https://duplicate-linked.test",
            publication_endpoint="https://duplicate-linked.test/api/content",
            project_status="duplicate",
        )
        db.add_all([removable, linked])
        db.flush()
        db.add(models.PromptTemplate(site_id=linked.id, name="Used", content="Prompt"))
        db.commit()

        result = delete_duplicate_sites(None, db)  # type: ignore[arg-type]

        assert result == {"deleted_count": 1, "skipped_count": 1}
        assert db.scalar(select(models.Site).where(models.Site.id == removable.id)) is None
        assert db.scalar(select(models.Site).where(models.Site.id == linked.id)) is not None
