from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from fastapi import Depends

from app.api import deps, exceptions
from app.entities import User
from app.security import TokenPayload

if TYPE_CHECKING:
    from fastapi import FastAPI
    from tests.conftest import TestClient

pytestmark = [pytest.mark.asyncio]


async def current_user_id(user_id: str = Depends(deps.current_user_id)):
    return {"user_id": user_id}


async def current_user(user: User = Depends(deps.current_user)):
    return {"user": user}


async def get_superuser(superuser: User = Depends(deps.superuser)):
    return {"user": superuser}


async def token_payload(payload: TokenPayload = Depends(deps.token_payload)):
    return {"payload": payload}


async def test_current_user_id(app: FastAPI, client: TestClient, user: User):
    app.add_api_route("/current_user_id", current_user_id)
    response = await client.login(user.id).get("/current_user_id")
    assert response.json()["user_id"] == str(user.id)
    assert response.status_code == 200


async def test_current_user_id_but_no_user_exists(app: FastAPI, client: TestClient):
    app.add_api_route("/current_user_id", current_user_id)
    fake_user_id = uuid.uuid4()
    response = await client.login(fake_user_id).get("/current_user_id")
    assert response.json() == exceptions.UserNotFound().as_dict()
    assert response.status_code == 404


async def test_current_user(app: FastAPI, client: TestClient, user: User):
    app.add_api_route("/current_user", current_user)
    response = await client.login(user.id).get("/current_user")
    assert User.parse_obj(response.json()["user"]) == user
    assert response.status_code == 200


async def test_current_user_but_no_user_exists(app: FastAPI, client: TestClient):
    app.add_api_route("/current_user", current_user)
    fake_user_id = uuid.uuid4()
    response = await client.login(fake_user_id).get("/current_user")
    assert response.json() == exceptions.UserNotFound().as_dict()
    assert response.status_code == 404


async def test_superuser(app: FastAPI, client: TestClient, superuser: User):
    app.add_api_route("/superuser", get_superuser)
    response = await client.login(superuser.id).get("/superuser")
    assert User.parse_obj(response.json()["user"]) == superuser
    assert response.status_code == 200


async def test_superuser_but_permission_denied(
    app: FastAPI, client: TestClient, user: User
):
    app.add_api_route("/superuser", get_superuser)
    response = await client.login(user.id).get("/superuser")
    assert response.json() == exceptions.PermissionDenied().as_dict()
    assert response.status_code == 403


async def test_token_payload(app: FastAPI, client: TestClient):
    app.add_api_route("/token_payload", token_payload)
    fake_user_id = uuid.uuid4()
    response = await client.login(fake_user_id).get("/token_payload")
    assert response.json()["payload"]["sub"] == str(fake_user_id)
    assert response.status_code == 200


async def test_token_payload_but_token_is_missing(app: FastAPI, client: TestClient):
    app.add_api_route("/token_payload", token_payload)
    response = await client.get("/token_payload")
    assert response.json() == exceptions.MissingToken().as_dict()
    assert response.status_code == 401


async def test_token_payload_but_token_is_invalid(app: FastAPI, client: TestClient):
    app.add_api_route("/token_payload", token_payload)
    headers = {"Authorization": "Bearer token"}
    response = await client.get("/token_payload", headers=headers)
    assert response.json() == exceptions.InvalidToken().as_dict()
    assert response.status_code == 403
