"""
llm_client.py — Provider-agnostic LLM client.

Supports Anthropic Claude and OpenAI GPT with a unified interface.
JSON extraction is handled here so stages never need to worry about parsing quirks.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Raw response wrapper
# ---------------------------------------------------------------------------

class RawLLMResponse:
    """Wraps the raw text returned by any LLM provider."""

    def __init__(self, content: str, model: str, usage: Dict[str, int]):
        self.content = content
        self.model = model
        self.usage = usage

    def parse_json(self) -> Dict[str, Any]:
        """
        Robustly extract a JSON object from the LLM response.
        Handles: plain JSON, markdown ```json blocks, and leading/trailing prose.
        """
        text = self.content.strip()

        # 1. Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2. Strip markdown code fences
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
        if fence_match:
            try:
                return json.loads(fence_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 3. Find the first {...} block
        brace_match = re.search(r"\{[\s\S]*\}", text)
        if brace_match:
            try:
                return json.loads(brace_match.group())
            except json.JSONDecodeError:
                pass

        raise ValueError(
            f"Could not extract valid JSON from LLM response.\n"
            f"Raw content (first 500 chars): {text[:500]}"
        )


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseLLMClient(ABC):
    """Common interface for all LLM providers."""

    @abstractmethod
    def complete(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> RawLLMResponse:
        """Send a completion request and return a RawLLMResponse."""

    def complete_json(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """Convenience wrapper: complete + parse JSON."""
        raw = self.complete(system, messages, max_tokens, temperature)
        return raw.parse_json()


# ---------------------------------------------------------------------------
# Anthropic implementation
# ---------------------------------------------------------------------------

class AnthropicClient(BaseLLMClient):
    """Wraps the Anthropic Messages API."""

    DEFAULT_MODEL = "claude-3-5-haiku-20241022"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ):
        try:
            import anthropic as _anthropic
        except ImportError as exc:
            raise ImportError(
                "The 'anthropic' package is required. Install it with: pip install anthropic"
            ) from exc

        resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not set. "
                "Export it or pass api_key= to AnthropicClient()."
            )

        self._client = _anthropic.Anthropic(api_key=resolved_key)
        self.model = model
        logger.info("AnthropicClient initialised (model=%s)", model)

    def complete(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> RawLLMResponse:
        t0 = time.perf_counter()
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
        )
        elapsed = time.perf_counter() - t0
        logger.debug(
            "Anthropic call completed in %.2fs | tokens in=%d out=%d",
            elapsed,
            resp.usage.input_tokens,
            resp.usage.output_tokens,
        )
        return RawLLMResponse(
            content=resp.content[0].text,
            model=self.model,
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
        )


# ---------------------------------------------------------------------------
# OpenAI implementation
# ---------------------------------------------------------------------------

class OpenAIClient(BaseLLMClient):
    """Wraps the OpenAI Chat Completions API with JSON response mode."""

    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ):
        try:
            from openai import OpenAI as _OpenAI
        except ImportError as exc:
            raise ImportError(
                "The 'openai' package is required. Install it with: pip install openai"
            ) from exc

        resolved_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_key:
            raise EnvironmentError(
                "OPENAI_API_KEY not set. "
                "Export it or pass api_key= to OpenAIClient()."
            )

        self._client = _OpenAI(api_key=resolved_key)
        self.model = model
        logger.info("OpenAIClient initialised (model=%s)", model)

    def complete(
        self,
        system: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.1,
    ) -> RawLLMResponse:
        openai_messages = [{"role": "system", "content": system}] + messages
        t0 = time.perf_counter()
        resp = self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=openai_messages,
            response_format={"type": "json_object"},
        )
        elapsed = time.perf_counter() - t0
        logger.debug(
            "OpenAI call completed in %.2fs | tokens in=%d out=%d",
            elapsed,
            resp.usage.prompt_tokens,
            resp.usage.completion_tokens,
        )
        return RawLLMResponse(
            content=resp.choices[0].message.content,
            model=self.model,
            usage={
                "input_tokens": resp.usage.prompt_tokens,
                "output_tokens": resp.usage.completion_tokens,
            },
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_llm_client(
    provider: str = "anthropic",
    **kwargs: Any,
) -> BaseLLMClient:
    """
    Factory function to instantiate the correct LLM client.

    Args:
        provider: "anthropic" or "openai"
        **kwargs: Passed directly to the client constructor (e.g. model=, api_key=)
    """
    providers = {
        "anthropic": AnthropicClient,
        "openai": OpenAIClient,
    }
    if provider not in providers:
        raise ValueError(
            f"Unknown provider '{provider}'. Choose from: {list(providers.keys())}"
        )
    return providers[provider](**kwargs)
