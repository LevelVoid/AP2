#!/usr/bin/env python3
"""Verification test harness for the Ollama AP2 integration.

Run with:
    python scripts/test_ollama_ap2.py

Checks:
1. Ollama endpoint reachable and the configured model is available.
2. FunctionCallResolver correctly maps an AP2 tool call through Ollama.
3. resolve_function_call returns the expected dict schema.
4. execute_with_retry retries on transient errors and re-raises on exhaustion.

Exit code 0 = all checks passed, non-zero = at least one failure.
"""

import json
import os
import sys
import unittest

# ---------------------------------------------------------------------------
# Allow running from the repo root without installing the package.
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_PATH = os.path.join(
    _REPO_ROOT, "code", "samples", "python", "src"
)
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

import openai  # noqa: E402  (after sys.path manipulation)
from common.constants import OLLAMA_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL  # noqa: E402
from common.function_call_resolver import FunctionCallResolver, _build_openai_tools  # noqa: E402
from common.retrying_llm_agent import execute_with_retry  # noqa: E402


# ---------------------------------------------------------------------------
# Dummy AP2 tool used in function-call tests
# ---------------------------------------------------------------------------

def create_checkout(cart_id: str) -> str:
    """Asks merchant to create a checkout JWT for the selected cart."""
    return f"checkout for {cart_id}"


def initiate_payment(mandate: str) -> str:
    """Initiates payment by sending mandate SD-JWTs to the merchant."""
    return f"payment initiated for {mandate}"


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------

class TestOllamaConfig(unittest.TestCase):
    """Basic config sanity checks."""

    def test_base_url_is_set(self):
        self.assertTrue(OLLAMA_BASE_URL.startswith("http"), OLLAMA_BASE_URL)

    def test_model_is_set(self):
        self.assertTrue(len(OLLAMA_MODEL) > 0, "OLLAMA_MODEL is empty")

    def test_api_key_is_set(self):
        self.assertTrue(len(OLLAMA_API_KEY) > 0, "OLLAMA_API_KEY is empty")


class TestBuildOpenAITools(unittest.TestCase):
    """Unit-tests for _build_openai_tools helper."""

    def test_schema_shape(self):
        tools = _build_openai_tools([create_checkout, initiate_payment])
        self.assertEqual(len(tools), 2)
        for t in tools:
            self.assertEqual(t["type"], "function")
            func = t["function"]
            self.assertIn("name", func)
            self.assertIn("description", func)
            self.assertIn("parameters", func)
            self.assertEqual(func["parameters"]["type"], "object")

    def test_names_match_callables(self):
        tools = _build_openai_tools([create_checkout, initiate_payment])
        names = {t["function"]["name"] for t in tools}
        self.assertIn("create_checkout", names)
        self.assertIn("initiate_payment", names)

    def test_description_is_first_docstring_line(self):
        tools = _build_openai_tools([create_checkout])
        desc = tools[0]["function"]["description"]
        self.assertIn("checkout", desc.lower())


class TestFunctionCallResolverUnit(unittest.TestCase):
    """Unit-tests for FunctionCallResolver using mocked openai client."""

    def _make_resolver(self, tool_call_name=None, text_reply=None):
        """Return a resolver whose internal OpenAI client is mocked."""
        import unittest.mock as mock

        resolver = FunctionCallResolver(
            tools=[create_checkout, initiate_payment],
            instructions="Pick the right AP2 tool.",
        )

        # Build a fake ChatCompletion response
        message = mock.MagicMock()
        if tool_call_name:
            tc = mock.MagicMock()
            tc.function.name = tool_call_name
            tc.function.arguments = json.dumps({"cart_id": "cart-123"})
            message.tool_calls = [tc]
            message.content = None
        else:
            message.tool_calls = None
            message.content = text_reply or "I don't know which tool to use."

        choice = mock.MagicMock()
        choice.message = message
        fake_response = mock.MagicMock()
        fake_response.choices = [choice]

        resolver._client.chat.completions.create = mock.MagicMock(
            return_value=fake_response
        )
        return resolver

    def test_resolve_returns_tool_name_and_args(self):
        resolver = self._make_resolver(tool_call_name="create_checkout")
        result = resolver.resolve_function_call(
            "Create a checkout for my cart", [create_checkout, initiate_payment]
        )
        self.assertEqual(result["name"], "create_checkout")
        self.assertIsInstance(result["args"], dict)
        self.assertIsNone(result["text"])

    def test_resolve_returns_text_when_no_tool(self):
        resolver = self._make_resolver(text_reply="Sorry, I cannot help.")
        result = resolver.resolve_function_call(
            "Tell me a joke", [create_checkout, initiate_payment]
        )
        self.assertIsNone(result["name"])
        self.assertIsNone(result["args"])
        self.assertIn("Sorry", result["text"])

    def test_determine_tool_returns_name(self):
        resolver = self._make_resolver(tool_call_name="initiate_payment")
        name = resolver.determine_tool_to_use("Initiate the payment now")
        self.assertEqual(name, "initiate_payment")

    def test_determine_tool_returns_unknown_when_no_call(self):
        resolver = self._make_resolver(text_reply="No tool needed.")
        name = resolver.determine_tool_to_use("Hello there")
        self.assertEqual(name, "Unknown")


class TestExecuteWithRetry(unittest.TestCase):
    """Unit-tests for the execute_with_retry helper."""

    def test_succeeds_on_first_attempt(self):
        result = execute_with_retry(lambda: 42, max_retries=3)
        self.assertEqual(result, 42)

    def test_retries_on_connection_error(self):
        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 3:
                raise openai.APIConnectionError(request=None)
            return "ok"

        result = execute_with_retry(flaky, max_retries=3, backoff_factor=0)
        self.assertEqual(result, "ok")
        self.assertEqual(call_count[0], 3)

    def test_reraises_after_exhaustion(self):
        def always_fails():
            raise openai.APITimeoutError(request=None)

        with self.assertRaises(openai.APITimeoutError):
            execute_with_retry(always_fails, max_retries=2, backoff_factor=0)

    def test_retries_on_json_decode_error(self):
        call_count = [0]

        def bad_json():
            call_count[0] += 1
            if call_count[0] == 1:
                raise json.JSONDecodeError("err", "", 0)
            return "parsed"

        result = execute_with_retry(bad_json, max_retries=2, backoff_factor=0)
        self.assertEqual(result, "parsed")


class TestOllamaLiveConnection(unittest.TestCase):
    """Integration smoke test — skipped when Ollama is unreachable."""

    @classmethod
    def setUpClass(cls):
        """Check Ollama is reachable; skip the class if not."""
        import urllib.request
        import urllib.error

        # The /v1/models endpoint lists available models.
        models_url = OLLAMA_BASE_URL.rstrip("/").replace("/v1", "") + "/api/tags"
        try:
            with urllib.request.urlopen(models_url, timeout=3) as resp:
                cls._models_data = json.loads(resp.read())
        except Exception as exc:  # noqa: BLE001
            raise unittest.SkipTest(
                f"Ollama not reachable at {OLLAMA_BASE_URL}: {exc}"
            ) from exc

    def test_model_is_available(self):
        """The configured OLLAMA_MODEL should be in the local model list."""
        names = [m.get("name", "") for m in self._models_data.get("models", [])]
        # Ollama names look like "gemma3:27b" or "gemma3:latest"
        short_name = OLLAMA_MODEL.split(":")[0]
        matches = [n for n in names if n.startswith(short_name)]
        self.assertTrue(
            matches,
            f"{OLLAMA_MODEL!r} not found in Ollama model list: {names}",
        )

    def test_live_function_call_resolution(self):
        """FunctionCallResolver should pick the right tool via Ollama."""
        resolver = FunctionCallResolver(
            tools=[create_checkout, initiate_payment],
            instructions=(
                "You are an AP2 payment agent. Choose the right tool."
            ),
        )
        try:
            result = resolver.resolve_function_call(
                "Create a checkout for cart 'cart-abc'",
                [create_checkout, initiate_payment],
            )
        except openai.BadRequestError as exc:
            if "does not support tools" in str(exc):
                raise unittest.SkipTest(
                    f"{OLLAMA_MODEL!r} does not support function calling. "
                    "Set OLLAMA_MODEL to a tool-capable model (e.g. gemma4:e4b, qwen3.5:9b-mlx)."
                ) from exc
            raise
        # Ollama should select create_checkout
        self.assertEqual(
            result.get("name"),
            "create_checkout",
            f"Unexpected result: {result}",
        )
        self.assertIsInstance(result.get("args"), dict)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"AP2 Ollama Test Harness")
    print(f"  OLLAMA_BASE_URL = {OLLAMA_BASE_URL}")
    print(f"  OLLAMA_MODEL    = {OLLAMA_MODEL}")
    print(f"  OLLAMA_API_KEY  = {OLLAMA_API_KEY}")
    print()
    unittest.main(verbosity=2)
