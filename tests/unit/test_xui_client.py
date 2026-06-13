from __future__ import annotations

import unittest

import httpx
from pydantic import SecretStr

from apps.api.agentvpn_api.integrations.xui.client import ThreeXUIApiClient
from apps.api.agentvpn_api.integrations.xui.errors import XuiApiError, XuiUnavailableError
from apps.api.agentvpn_api.integrations.xui.models import XuiClientCreate
from apps.api.agentvpn_api.integrations.xui.settings import XuiSettings


def settings(**overrides: object) -> XuiSettings:
    values: dict[str, object] = {
        "base_url": "https://vpn.example.com/secret-panel/",
        "api_token": SecretStr("test-token"),
        "safe_retry_attempts": 2,
        "circuit_failure_threshold": 3,
    }
    values.update(overrides)
    return XuiSettings.model_validate(values)


class XuiClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_bearer_token_is_sent(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["Authorization"], "Bearer test-token")
            return httpx.Response(
                200,
                json={"success": True, "obj": {"cpu": 1, "xray": {"state": "running"}}},
            )

        client = ThreeXUIApiClient(settings(), transport=httpx.MockTransport(handler))
        async with client:
            await client.health_check()

    async def test_session_login_is_used_after_token_rejection(self) -> None:
        calls: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            if request.url.path.endswith("/login"):
                return httpx.Response(
                    200,
                    headers={"set-cookie": "3x-ui=session-value; Path=/"},
                    json={"success": True},
                )
            if "3x-ui=session-value" not in request.headers.get("cookie", ""):
                return httpx.Response(401, json={"success": False})
            return httpx.Response(
                200,
                json={"success": True, "obj": {"cpu": 1, "xray": {"state": "running"}}},
            )

        client = ThreeXUIApiClient(
            settings(username="admin", password=SecretStr("password")),
            transport=httpx.MockTransport(handler),
        )
        async with client:
            await client.health_check()

        self.assertEqual(calls.count("/secret-panel/login"), 1)

    async def test_create_is_not_retried(self) -> None:
        attempts = 0

        async def handler(_: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            raise httpx.ConnectError("temporary")

        client = ThreeXUIApiClient(settings(), transport=httpx.MockTransport(handler))
        async with client:
            with self.assertRaises(XuiUnavailableError):
                await client.create_client(
                    XuiClientCreate(email="tg_1_2_vless", expiryTime=0),
                    [1],
                )

        self.assertEqual(attempts, 1)

    async def test_mutation_gets_one_authentication_retry(self) -> None:
        calls: list[str] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url.path)
            if request.url.path.endswith("/login"):
                return httpx.Response(
                    200,
                    headers={"set-cookie": "3x-ui=session-value; Path=/"},
                    json={"success": True},
                )
            if "3x-ui=session-value" not in request.headers.get("cookie", ""):
                return httpx.Response(401, json={"success": False})
            return httpx.Response(200, json={"success": True})

        client = ThreeXUIApiClient(
            settings(username="admin", password=SecretStr("password")),
            transport=httpx.MockTransport(handler),
        )
        async with client:
            await client.create_client(
                XuiClientCreate(email="tg_1_2_vless", expiryTime=0),
                [1],
            )

        self.assertEqual(calls.count("/secret-panel/panel/api/clients/add"), 2)

    async def test_unknown_get_client_error_does_not_look_like_absent_client(self) -> None:
        async def handler(_: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"success": False, "msg": "database unavailable"})

        client = ThreeXUIApiClient(settings(), transport=httpx.MockTransport(handler))
        async with client:
            with self.assertRaises(XuiApiError):
                await client.get_client("tg_1_2_vless")

    async def test_safe_get_is_retried(self) -> None:
        attempts = 0

        async def handler(_: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise httpx.ConnectError("temporary")
            return httpx.Response(
                200,
                json={"success": True, "obj": {"cpu": 1, "xray": {"state": "running"}}},
            )

        client = ThreeXUIApiClient(settings(), transport=httpx.MockTransport(handler))
        async with client:
            await client.health_check()

        self.assertEqual(attempts, 2)


if __name__ == "__main__":
    unittest.main()
