from typing import ClassVar

import pytest
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect, status
from fastapi.testclient import TestClient
from starlette.requests import HTTPConnection
from starlette.status import WS_1008_POLICY_VIOLATION

from fastapi_has_permissions import Permission, Policy, Requires, add_permissions
from fastapi_has_permissions.common import Allow, Deny


class HasAuthorizationHeader(Permission):
    # the same permission serves an HTTP route and a websocket one - it reads what both carry
    async def check_permissions(self, connection: HTTPConnection) -> bool:
        return "authorization" in connection.headers


class NeedsQueryParam(Permission):
    default_exc_message: ClassVar[str] = "no ticket"

    async def check_permissions(self, ticket: str) -> bool:
        return ticket == "granted"


class ReadOnly(Policy[None]):
    read = Allow()
    default = Deny()


@pytest.fixture
def app() -> FastAPI:
    app = FastAPI()
    add_permissions(app)

    @app.get("/http", dependencies=[Depends(HasAuthorizationHeader())])
    async def http_route() -> str:
        return "ok"

    @app.websocket("/ws", dependencies=[Depends(HasAuthorizationHeader())])
    async def ws_route(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text("ok")
        await websocket.close()

    @app.websocket("/ws-unresolved", dependencies=[Depends(NeedsQueryParam())])
    async def ws_unresolved(websocket: WebSocket) -> None:  # pragma: no cover - never reached
        await websocket.accept()

    @app.websocket("/ws-policy", dependencies=[Requires(ReadOnly())])
    async def ws_policy(websocket: WebSocket) -> None:  # pragma: no cover - never reached
        await websocket.accept()

    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_permission_allows_websocket(client: TestClient) -> None:
    with client.websocket_connect("/ws", headers={"Authorization": "token"}) as ws:
        assert ws.receive_text() == "ok"


def test_permission_denies_websocket(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect("/ws") as ws:
        ws.receive_text()

    assert exc_info.value.code == WS_1008_POLICY_VIOLATION
    assert exc_info.value.reason == "Permission denied"


def test_permission_denies_http_the_same_way(client: TestClient) -> None:
    assert client.get("/http").status_code == status.HTTP_403_FORBIDDEN
    assert client.get("/http", headers={"Authorization": "token"}).status_code == status.HTTP_200_OK


def test_unresolved_dependency_closes_websocket(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect("/ws-unresolved") as ws:
        ws.receive_text()

    assert exc_info.value.code == WS_1008_POLICY_VIOLATION


def test_policy_on_websocket_falls_back_to_default(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect("/ws-policy") as ws:
        ws.receive_text()

    assert exc_info.value.code == WS_1008_POLICY_VIOLATION
