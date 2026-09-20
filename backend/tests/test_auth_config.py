import asyncio
import unittest

from services.auth_config import (
    apply_auth_to_headers,
    execute_with_auth_retry,
    get_auth_config,
    has_auth_header,
    normalize_auth_config,
    resolve_auth_headers,
)


class AuthConfigTests(unittest.TestCase):
    def test_normalize_legacy_token_config_as_default_auth(self):
        cfg = normalize_auth_config({
            "url": "https://example.test/login",
            "method": "POST",
            "jsonpath": "$.data.token",
            "token_prefix": "Bearer ",
            "header_key": "Authorization",
            "enabled": True,
        })

        self.assertEqual(cfg["default_auth_key"], "default")
        self.assertEqual(cfg["items"][0]["key"], "default")
        self.assertEqual(cfg["items"][0]["url"], "https://example.test/login")
        self.assertEqual(cfg["items"][0]["header_key"], "Authorization")

    def test_get_auth_config_prefers_service_auth_over_default(self):
        auth_config = normalize_auth_config({
            "default_auth_key": "default",
            "items": [
                {"key": "default", "name": "默认认证", "manual_token": "env-token", "enabled": False},
                {"key": "resident", "name": "居民端认证", "manual_token": "resident-token", "enabled": False},
            ],
        })
        service = {"key": "resident-api", "auth_key": "resident"}

        selected, source = get_auth_config(auth_config, service)

        self.assertEqual(selected["key"], "resident")
        self.assertEqual(source, "service")

    def test_has_auth_header_is_case_insensitive(self):
        self.assertTrue(has_auth_header({"authorization": "Bearer abc"}, "Authorization"))
        self.assertTrue(has_auth_header({"X-Auth-Token": "abc"}, "x-auth-token"))
        self.assertFalse(has_auth_header({"Content-Type": "application/json"}, "Authorization"))

    def test_apply_auth_to_headers_preserves_existing_auth_header(self):
        headers = {"Authorization": "Bearer manual"}

        applied = apply_auth_to_headers(headers, "fresh-token", {
            "header_key": "Authorization",
            "token_prefix": "Bearer ",
        })

        self.assertEqual(applied["Authorization"], "Bearer manual")

    def test_resolve_auth_headers_reuses_execution_context_token(self):
        calls = []

        async def fetcher(auth, auth_key):
            calls.append(auth_key)
            return "token-" + auth_key

        async def run():
            auth_config = normalize_auth_config({
                "default_auth_key": "default",
                "items": [
                    {"key": "default", "enabled": True, "url": "https://example.test/login"},
                ],
            })
            context = {}

            first = await resolve_auth_headers(
                headers={},
                auth_config=auth_config,
                service=None,
                token_fetcher=fetcher,
                execution_context=context,
            )
            second = await resolve_auth_headers(
                headers={},
                auth_config=auth_config,
                service=None,
                token_fetcher=fetcher,
                execution_context=context,
            )
            return first, second

        first, second = asyncio.run(run())

        self.assertEqual(first.headers["Authorization"], "Bearer token-default")
        self.assertEqual(second.headers["Authorization"], "Bearer token-default")
        self.assertEqual(calls, ["default"])

    def test_resolve_auth_headers_overrides_environment_header_when_not_explicit(self):
        async def fetcher(auth, auth_key):
            return "fresh"

        async def run():
            auth_config = normalize_auth_config({
                "default_auth_key": "default",
                "items": [
                    {"key": "default", "enabled": True, "url": "https://example.test/login"},
                ],
            })
            return await resolve_auth_headers(
                headers={"Authorization": "Bearer old-env-token"},
                auth_config=auth_config,
                service=None,
                token_fetcher=fetcher,
                explicit_auth_header=False,
            )

        result = asyncio.run(run())

        self.assertEqual(result.headers["Authorization"], "Bearer fresh")

    def test_resolve_auth_headers_reuses_cached_token_across_requests(self):
        calls = []

        async def fetcher(auth, auth_key):
            calls.append(auth_key)
            return "cached-token"

        async def run():
            auth_config = normalize_auth_config({
                "default_auth_key": "default",
                "items": [
                    {"key": "default", "enabled": True, "url": "https://example.test/login"},
                ],
            })
            first = await resolve_auth_headers(
                headers={},
                auth_config=auth_config,
                service=None,
                token_fetcher=fetcher,
                auth_cache_scope="auth-cache-test",
            )
            second = await resolve_auth_headers(
                headers={},
                auth_config=auth_config,
                service=None,
                token_fetcher=fetcher,
                auth_cache_scope="auth-cache-test",
            )
            return first, second

        first, second = asyncio.run(run())

        self.assertEqual(first.token, "cached-token")
        self.assertEqual(second.token, "cached-token")
        self.assertEqual(calls, ["default"])

    def test_auth_failure_refreshes_token_and_retries_once(self):
        token_calls = []
        request_tokens = []

        async def fetcher(auth, auth_key):
            token = f"token-{len(token_calls) + 1}"
            token_calls.append(token)
            return token

        async def request(headers):
            token = headers["Authorization"]
            request_tokens.append(token)
            if token.endswith("token-1"):
                return {"response": {"status_code": 401, "body": {"code": 401}}}
            return {"response": {"status_code": 200, "body": {"code": 200}}}

        async def run():
            auth_config = normalize_auth_config({
                "default_auth_key": "default",
                "items": [
                    {"key": "default", "enabled": True, "url": "https://example.test/login"},
                ],
            })
            return await execute_with_auth_retry(
                headers={},
                auth_config=auth_config,
                service=None,
                token_fetcher=fetcher,
                request_func=request,
                auth_cache_scope="auth-retry-test",
            )

        result, resolution = asyncio.run(run())

        self.assertEqual(request_tokens, ["Bearer token-1", "Bearer token-2"])
        self.assertEqual(token_calls, ["token-1", "token-2"])
        self.assertEqual(result["response"]["status_code"], 200)
        self.assertEqual(resolution.token, "token-2")

    def test_auth_failure_after_refresh_does_not_retry_again(self):
        token_calls = []
        request_count = 0

        async def fetcher(auth, auth_key):
            token = f"token-{len(token_calls) + 1}"
            token_calls.append(token)
            return token

        async def request(headers):
            nonlocal request_count
            request_count += 1
            return {"response": {"status_code": 401, "body": {"code": 401}}}

        async def run():
            auth_config = normalize_auth_config({
                "default_auth_key": "default",
                "items": [
                    {"key": "default", "enabled": True, "url": "https://example.test/login"},
                ],
            })
            return await execute_with_auth_retry(
                headers={},
                auth_config=auth_config,
                service=None,
                token_fetcher=fetcher,
                request_func=request,
                auth_cache_scope="auth-no-loop-test",
            )

        result, _ = asyncio.run(run())

        self.assertEqual(request_count, 2)
        self.assertEqual(token_calls, ["token-1", "token-2"])
        self.assertEqual(result["response"]["status_code"], 401)

    def test_non_auth_failure_does_not_refresh_token(self):
        token_calls = []
        request_count = 0

        async def fetcher(auth, auth_key):
            token_calls.append(auth_key)
            return "token-1"

        async def request(headers):
            nonlocal request_count
            request_count += 1
            return {"response": {"status_code": 500, "body": {"code": 500}}}

        async def run():
            auth_config = normalize_auth_config({
                "default_auth_key": "default",
                "items": [
                    {"key": "default", "enabled": True, "url": "https://example.test/login"},
                ],
            })
            return await execute_with_auth_retry(
                headers={},
                auth_config=auth_config,
                service=None,
                token_fetcher=fetcher,
                request_func=request,
                auth_cache_scope="auth-business-failure-test",
            )

        result, _ = asyncio.run(run())

        self.assertEqual(request_count, 1)
        self.assertEqual(token_calls, ["default"])
        self.assertEqual(result["response"]["status_code"], 500)


if __name__ == "__main__":
    unittest.main()
