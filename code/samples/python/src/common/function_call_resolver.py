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

"""This module provides a FunctionCallResolver class.

The FunctionCallResolver uses an Ollama-hosted LLM (via the OpenAI-compatible
API) to determine which tool to use based on the instructions provided.
"""

import json
import logging

from collections.abc import Callable
from typing import Any, Optional

import openai

from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import Task
from common.constants import OLLAMA_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL


DataPartContent = dict[str, Any]
Tool = Callable[[list[DataPartContent], TaskUpdater, Task | None], Any]

_logger = logging.getLogger(__name__)


class FunctionCallResolver:
  """Resolves a natural language prompt to the name of a tool.

  Uses an Ollama-hosted model via the OpenAI-compatible API to pick the
  right tool function for an incoming A2A request.
  """

  def __init__(
      self,
      # Legacy positional arg kept for backward compatibility with
      # BaseServerExecutor which passes (client, tools, system_prompt).
      _legacy_client: Any = None,
      tools: list[Tool] | None = None,
      instructions: str = "You are a helpful assistant.",
      model_name: Optional[str] = None,
  ):
    """Initialise the resolver.

    Args:
      _legacy_client: Ignored.  Present only so existing callers that pass a
        ``genai.Client`` as the first positional argument do not break.
      tools: The list of AP2 tool callables whose names/docstrings are used to
        build the OpenAI function-call schema.
      instructions: System prompt that steers the model.
      model_name: Override the Ollama model.  Falls back to ``OLLAMA_MODEL``.
    """
    self._model = model_name or OLLAMA_MODEL
    self._instructions = instructions
    self._tools: list[Tool] = tools or []

    self._client = openai.OpenAI(
        base_url=OLLAMA_BASE_URL,
        api_key=OLLAMA_API_KEY,
    )
    _logger.info(
        "FunctionCallResolver: Ollama endpoint=%s  model=%s",
        OLLAMA_BASE_URL,
        self._model,
    )

  # ------------------------------------------------------------------
  # Public API
  # ------------------------------------------------------------------

  def determine_tool_to_use(self, prompt: str) -> str:
    """Determine which tool name to call for *prompt*.

    Args:
      prompt: The incoming text prompt from an A2A request.

    Returns:
      The ``__name__`` of the chosen tool, or ``"Unknown"`` if the model
      does not select one.
    """
    result = self.resolve_function_call(prompt, self._tools)
    name = result.get("name")
    if name:
      _logger.debug("FunctionCallResolver selected tool: %s", name)
      return name
    _logger.warning(
        "FunctionCallResolver: no tool_call returned. text=%s",
        result.get("text", ""),
    )
    return "Unknown"

  def resolve_function_call(
      self,
      prompt: str,
      tools: list[Tool],
  ) -> dict[str, Any]:
    """Ask Ollama to pick a tool function and parse its arguments.

    Args:
      prompt: Raw text prompt or conversation-context string.
      tools: AP2 tool callables; their ``__name__`` and ``__doc__`` are used
        to build the OpenAI function schema.

    Returns:
      A dict with the schema::

        {
          "name":  str | None,   # function name chosen by the model
          "args":  dict | None,  # parsed keyword arguments
          "text":  str | None,   # model text when no tool was called
        }
    """
    openai_tools = _build_openai_tools(tools)

    messages = [
        {"role": "system", "content": self._instructions},
        {"role": "user", "content": prompt},
    ]

    _logger.debug(
        "resolve_function_call → model=%s  tools=%s",
        self._model,
        [t["function"]["name"] for t in openai_tools],
    )

    response = self._client.chat.completions.create(
        model=self._model,
        messages=messages,
        tools=openai_tools,
        tool_choice="auto",
    )

    message = response.choices[0].message

    if message.tool_calls:
      call = message.tool_calls[0]
      func_name = call.function.name
      try:
        args = json.loads(call.function.arguments)
      except (json.JSONDecodeError, TypeError):
        args = {}
      _logger.debug("resolve_function_call: tool_call name=%s args=%s", func_name, args)
      return {"name": func_name, "args": args, "text": None}

    text = message.content or ""
    _logger.debug("resolve_function_call: no tool_call, text=%r", text)
    return {"name": None, "args": None, "text": text}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_openai_tools(tools: list[Tool]) -> list[dict[str, Any]]:
  """Convert AP2 tool callables to the OpenAI function-call schema format.

  Args:
    tools: List of Python callables that represent AP2 agent tools.

  Returns:
    A list of dicts in the format expected by ``openai.chat.completions.create``.
  """
  result = []
  for tool in tools:
    result.append({
        "type": "function",
        "function": {
            "name": tool.__name__,
            "description": (tool.__doc__ or "").strip().splitlines()[0],
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    })
  return result
