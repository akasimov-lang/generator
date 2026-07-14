import pytest
from fastapi import HTTPException

from app.security import require_admin


def test_require_admin_rejects_regular_user() -> None:
    with pytest.raises(HTTPException) as exc:
        require_admin({"id": "user-id", "username": "editor", "is_admin": False})

    assert exc.value.status_code == 403


def test_require_admin_allows_admin_user() -> None:
    user = {"id": "admin-id", "username": "admin", "is_admin": True}

    assert require_admin(user) == user
