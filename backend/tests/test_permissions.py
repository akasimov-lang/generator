import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.api import reset_user_password
from app.db import Base
from app.security import hash_password, require_admin, verify_password


def test_require_admin_rejects_regular_user() -> None:
    with pytest.raises(HTTPException) as exc:
        require_admin({"id": "user-id", "username": "editor", "is_admin": False})

    assert exc.value.status_code == 403


def test_require_admin_allows_admin_user() -> None:
    user = {"id": "admin-id", "username": "admin", "is_admin": True}

    assert require_admin(user) == user


def test_admin_can_reset_user_password_and_receives_it_once() -> None:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        user = models.User(username="arseniy", password_hash=hash_password("old-password"), is_active=True)
        db.add(user)
        db.commit()

        result = reset_user_password(user.id, {"id": "admin-id", "username": "admin", "is_admin": True}, db)  # type: ignore[arg-type]

        db.refresh(user)
        assert len(result["password"]) >= 16
        assert verify_password(result["password"], user.password_hash)
        assert not verify_password("old-password", user.password_hash)
