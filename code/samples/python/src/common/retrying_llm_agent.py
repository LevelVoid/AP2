# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""An LLM agent that surfaces errors to the user and then retries.

This implementation enhances the ADK's LlmAgent by automatically retrying
requests and surfacing errors captured from the LLM (Ollama or any
OpenAI-compatible endpoint).
"""

import json
import logging
import time
import traceback

import sys

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

from collections.abc import Callable
from typing import TypeVar

import openai

from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.llm_agent import LlmAgent
from google.adk.events.event import Event
from typing_extensions import AsyncGenerator


_logger = logging.getLogger(__name__)

T = TypeVar("T")

# Transient errors that warrant a retry against the Ollama endpoint.
_RETRYABLE_ERRORS = (
    openai.APIConnectionError,
    openai.APITimeoutError,
    json.JSONDecodeError,
)


def execute_with_retry(
    func: Callable[[], T],
    max_retries: int = 3,
    backoff_factor: float = 1.5,
) -> T:
  """Call *func* with exponential back-off retries on transient Ollama errors.

  Args:
    func: A zero-argument callable to attempt.
    max_retries: Maximum number of additional attempts after the first failure.
    backoff_factor: Multiplied by the attempt index to compute sleep duration.

  Returns:
    The return value of *func* on success.

  Raises:
    The last caught exception when all attempts are exhausted.
  """
  last_exc: Exception | None = None
  for attempt in range(max_retries + 1):
    try:
      return func()
    except _RETRYABLE_ERRORS as exc:
      last_exc = exc
      if attempt < max_retries:
        sleep_secs = backoff_factor * (attempt + 1)
        _logger.warning(
            "execute_with_retry: attempt %d/%d failed (%s: %s). "
            "Retrying in %.1f s …",
            attempt + 1,
            max_retries + 1,
            type(exc).__name__,
            exc,
            sleep_secs,
        )
        time.sleep(sleep_secs)
      else:
        _logger.error(
            "execute_with_retry: all %d attempts exhausted. Last error: %s",
            max_retries + 1,
            exc,
        )
  raise last_exc  # type: ignore[misc]


class RetryingLlmAgent(LlmAgent):
  """An LLM agent that surfaces errors to the user and then retries.

  Catches both Ollama/OpenAI transient errors and generic exceptions so that
  transient backend hiccups don't crash the entire agent session.
  """

  def __init__(self, *args, max_retries: int = 1, **kwargs):
    super().__init__(*args, **kwargs)
    self._max_retries = max_retries

  async def _retry_async(
      self, ctx: InvocationContext, retries_left: int = 0
  ) -> AsyncGenerator[Event, None]:
    if retries_left <= 0:
      yield Event(
          author=ctx.agent.name,
          invocation_id=ctx.invocation_id,
          error_message=(
              "Maximum retries exhausted. The Ollama inference server failed to"
              " respond. Please check that Ollama is running and try again."
          ),
      )
    else:
      try:
        async for event in super()._run_async_impl(ctx):
          yield event
      except _RETRYABLE_ERRORS as e:
        _logger.error(
            "%s: caught transient Ollama error %s (retries_left=%s): %s\n%s",
            ctx.agent.name,
            type(e).__name__,
            retries_left,
            e,
            traceback.format_exc(),
        )
        yield Event(
            author=ctx.agent.name,
            invocation_id=ctx.invocation_id,
            error_message=(
                f"Ollama server error ({type(e).__name__}: {e}). Retrying…"
            ),
            custom_metadata={
                "error_type": type(e).__name__,
                "error": str(e),
            },
        )
        async for event in self._retry_async(ctx, retries_left - 1):
          yield event
      except Exception as e:  # pylint: disable=broad-exception-caught
        _logger.error(
            "%s: caught unexpected error %s (retries_left=%s): %s\n%s",
            ctx.agent.name,
            type(e).__name__,
            retries_left,
            e,
            traceback.format_exc(),
        )
        yield Event(
            author=ctx.agent.name,
            invocation_id=ctx.invocation_id,
            error_message=(
                f"Agent error ({type(e).__name__}: {e}). Retrying…"
            ),
            custom_metadata={
                "error_type": type(e).__name__,
                "error": str(e),
            },
        )
        async for event in self._retry_async(ctx, retries_left - 1):
          yield event

  @override
  async def _run_async_impl(
      self, ctx: InvocationContext
  ) -> AsyncGenerator[Event, None]:
    async for event in self._retry_async(ctx, retries_left=self._max_retries):
      _logger.info("RetryingLlmAgent Event: %s", getattr(event, 'model_dump_json', lambda: str(event))())
      yield event
