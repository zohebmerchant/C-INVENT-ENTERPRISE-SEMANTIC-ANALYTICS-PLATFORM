"""
Enterprise Semantic Analytics Platform
--------------------------------------

Capgemini Enterprise LLM adapter.

Important:
The Capgemini endpoint used by the existing working application is:

    https://api.generative.engine.capgemini.com/v2/11m/invoke

The previous application configured the provider as "azure" because
it used Azure-style authentication/client behavior against the
Capgemini endpoint.

This implementation keeps the platform provider-neutral while
supporting the Capgemini gateway explicitly.

Supported:

    AI_PROVIDER = "capgemini"

    AI_PROVIDER = "azure"

    AI_PROVIDER = "openai_compatible"
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import requests
import streamlit as st


# =============================================================================
# RESULT
# =============================================================================


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str


# =============================================================================
# SECRET HELPERS
# =============================================================================


def _secret(
    name: str,
    default: str = "",
) -> str:
    """
    Read a Streamlit secret safely.

    Secret values are never logged or displayed.
    """

    try:
        value = st.secrets.get(
            name,
            default,
        )
    except Exception:
        value = default

    if value is None:
        return default

    return str(value).strip()


# =============================================================================
# PROVIDER
# =============================================================================


def provider_name() -> str:
    """
    Return the configured AI provider.

    For the current Invent deployment this should be:

        capgemini
    """

    provider = _secret(
        "AI_PROVIDER",
        "",
    ).lower()

    if provider:
        return provider

    # Automatic fallback detection.
    if (
        _secret("CAPGEMINI_LLM_BASE_URL")
        and _secret("CAPGEMINI_LLM_API_KEY")
    ):
        return "capgemini"

    if (
        _secret("AZURE_OPENAI_ENDPOINT")
        and _secret("AZURE_OPENAI_API_KEY")
    ):
        return "azure"

    if (
        _secret("LLM_BASE_URL")
        and _secret("LLM_API_KEY")
    ):
        return "openai_compatible"

    return "none"


# =============================================================================
# CONFIGURATION STATUS
# =============================================================================


def configuration_status() -> dict[str, Any]:
    """
    Return safe configuration diagnostics.

    IMPORTANT:
    This never returns API-key values.
    """

    provider = provider_name()

    # -------------------------------------------------------------------------
    # Capgemini
    # -------------------------------------------------------------------------

    if provider == "capgemini":

        required = {
            "CAPGEMINI_LLM_BASE_URL":
                bool(
                    _secret(
                        "CAPGEMINI_LLM_BASE_URL"
                    )
                ),

            "CAPGEMINI_LLM_API_KEY":
                bool(
                    _secret(
                        "CAPGEMINI_LLM_API_KEY"
                    )
                ),

            "CAPGEMINI_LLM_MODEL":
                bool(
                    _secret(
                        "CAPGEMINI_LLM_MODEL"
                    )
                ),
        }

        missing = [
            key
            for key, present
            in required.items()
            if not present
        ]

        return {
            "provider": "capgemini",
            "available": len(missing) == 0,
            "missing": missing,
        }

    # -------------------------------------------------------------------------
    # Azure
    # -------------------------------------------------------------------------

    if provider == "azure":

        required = {
            "AZURE_OPENAI_ENDPOINT":
                bool(
                    _secret(
                        "AZURE_OPENAI_ENDPOINT"
                    )
                ),

            "AZURE_OPENAI_API_KEY":
                bool(
                    _secret(
                        "AZURE_OPENAI_API_KEY"
                    )
                ),

            "AZURE_OPENAI_DEPLOYMENT":
                bool(
                    _secret(
                        "AZURE_OPENAI_DEPLOYMENT"
                    )
                ),
        }

        missing = [
            key
            for key, present
            in required.items()
            if not present
        ]

        return {
            "provider": "azure",
            "available": len(missing) == 0,
            "missing": missing,
        }

    # -------------------------------------------------------------------------
    # Generic OpenAI-compatible
    # -------------------------------------------------------------------------

    if provider in {
        "openai_compatible",
        "enterprise",
    }:

        required = {
            "LLM_BASE_URL":
                bool(
                    _secret(
                        "LLM_BASE_URL"
                    )
                ),

            "LLM_API_KEY":
                bool(
                    _secret(
                        "LLM_API_KEY"
                    )
                ),

            "LLM_MODEL":
                bool(
                    _secret(
                        "LLM_MODEL"
                    )
                ),
        }

        missing = [
            key
            for key, present
            in required.items()
            if not present
        ]

        return {
            "provider": provider,
            "available": len(missing) == 0,
            "missing": missing,
        }

    return {
        "provider": "none",
        "available": False,
        "missing": [],
    }


def is_available() -> bool:
    return bool(
        configuration_status()[
            "available"
        ]
    )


# =============================================================================
# CAPGEMINI AUTHENTICATION
# =============================================================================


def _capgemini_headers() -> dict[str, str]:
    """
    Build Capgemini request headers.

    IMPORTANT:
    The default is api-key rather than:

        Authorization: Bearer ...

    because the previous working project used an Azure-style client
    against the Capgemini endpoint.

    The header can be overridden through:

        CAPGEMINI_AUTH_HEADER

    if Capgemini's enterprise gateway specifies another header.
    """

    api_key = _secret(
        "CAPGEMINI_LLM_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "CAPGEMINI_LLM_API_KEY is missing."
        )

    auth_header = _secret(
        "CAPGEMINI_AUTH_HEADER",
        "api-key",
    )

    return {
        auth_header: api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# =============================================================================
# CAPGEMINI REQUEST BODY
# =============================================================================


def _capgemini_payload(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    """
    Build the request payload.

    The model shown in the existing working project is:

        openai.gpt-5.1
    """

    model = _secret(
        "CAPGEMINI_LLM_MODEL"
    )

    if not model:

        raise RuntimeError(
            "CAPGEMINI_LLM_MODEL is missing."
        )

    return {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }


# =============================================================================
# CAPGEMINI RESPONSE EXTRACTION
# =============================================================================


def _extract_capgemini_text(
    data: Any,
) -> str:
    """
    Extract text from the common response shapes.

    Supports:

        choices[0].message.content

    and several common gateway variants.

    We intentionally do not silently fabricate a response.
    """

    if not isinstance(
        data,
        dict,
    ):

        raise RuntimeError(
            "Capgemini returned a non-object response."
        )

    # -------------------------------------------------------------------------
    # OpenAI-compatible response
    # -------------------------------------------------------------------------

    choices = data.get(
        "choices"
    )

    if isinstance(
        choices,
        list,
    ) and choices:

        first = choices[0]

        if isinstance(
            first,
            dict,
        ):

            message = first.get(
                "message"
            )

            if isinstance(
                message,
                dict,
            ):

                content = message.get(
                    "content"
                )

                if content is not None:

                    if isinstance(
                        content,
                        list,
                    ):

                        parts = []

                        for item in content:

                            if isinstance(
                                item,
                                dict,
                            ):

                                text = item.get(
                                    "text"
                                )

                                if text:
                                    parts.append(
                                        str(text)
                                    )

                        if parts:
                            return "\n".join(
                                parts
                            )

                    return str(
                        content
                    ).strip()

            text = first.get(
                "text"
            )

            if text:
                return str(
                    text
                ).strip()

    # -------------------------------------------------------------------------
    # Common direct response shapes
    # -------------------------------------------------------------------------

    for key in (
        "output",
        "response",
        "text",
        "content",
        "answer",
    ):

        value = data.get(
            key
        )

        if isinstance(
            value,
            str,
        ) and value.strip():

            return value.strip()

    # -------------------------------------------------------------------------
    # Nested output
    # -------------------------------------------------------------------------

    output = data.get(
        "output"
    )

    if isinstance(
        output,
        dict,
    ):

        for key in (
            "text",
            "content",
            "response",
        ):

            value = output.get(
                key
            )

            if isinstance(
                value,
                str,
            ) and value.strip():

                return value.strip()

    # -------------------------------------------------------------------------
    # No known response shape
    # -------------------------------------------------------------------------

    raise RuntimeError(
        "Capgemini response did not contain "
        "recognizable generated text. "
        f"Response keys: {list(data.keys())}"
    )


# =============================================================================
# CAPGEMINI CHAT
# =============================================================================


def _chat_capgemini(
    messages: list[dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 1200,
) -> LLMResult:

    import uuid

    base_url = _secret(
        "CAPGEMINI_LLM_BASE_URL"
    ).rstrip("/")

    api_key = _secret(
        "CAPGEMINI_LLM_API_KEY"
    )

    model = _secret(
        "CAPGEMINI_LLM_MODEL",
        "openai.gpt-5.1",
    )

    if not base_url:
        raise RuntimeError(
            "CAPGEMINI_LLM_BASE_URL is missing."
        )

    if not api_key:
        raise RuntimeError(
            "CAPGEMINI_LLM_API_KEY is missing."
        )

    # ---------------------------------------------------------------
    # Build prompt
    # ---------------------------------------------------------------

    system_parts = []
    user_parts = []

    for message in messages:

        role = str(
            message.get("role", "")
        ).lower()

        content = str(
            message.get("content", "")
        )

        if role == "system":
            system_parts.append(content)

        elif role == "user":
            user_parts.append(content)

        elif role == "assistant":
            user_parts.append(
                f"Previous assistant response:\n{content}"
            )

    system_prompt = "\n\n".join(
        system_parts
    ).strip()

    user_text = "\n\n".join(
        user_parts
    ).strip()

    if not system_prompt:
        system_prompt = (
            "You are an enterprise analytics assistant. "
            "Answer using only the governed semantic "
            "model supplied by the application."
        )

    # ---------------------------------------------------------------
    # Session
    # ---------------------------------------------------------------

    session_id = str(
        uuid.uuid4()
    )

    workspace_id = _secret(
        "CAPGEMINI_WORKSPACE_ID",
        "",
    )

    # ---------------------------------------------------------------
    # Capgemini /v2/11m/invoke request
    # ---------------------------------------------------------------

    payload = {
        "action": "run",

        "modelInterface": "langchain",

        "data": {
            "mode": "chain",

            "text": user_text,

            "files": [],

            "modelName": model,

            # Your previous working project uses Azure
            # as the model provider for openai.gpt-5.1.
            "provider": "azure",

            "systemPrompt": system_prompt,

            "sessionId": session_id,

            "modelKwargs": {
                "maxTokens": max_tokens,
                "temperature": temperature,
                "streaming": False,
                "topP": 0.9,
            },
        },
    }

    # Only include workspaceId if your Capgemini
    # environment actually requires/provides one.
    if workspace_id:
        payload["data"]["workspaceId"] = workspace_id

    # ---------------------------------------------------------------
    # Authentication
    #
    # Capgemini documentation:
    #
    # ApiKeyAuth
    # Name: x-api-key
    # In: header
    # ---------------------------------------------------------------

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-api-key": api_key,
    }

    timeout = int(
        _secret(
            "LLM_TIMEOUT_SECONDS",
            "90",
        )
    )

    try:

        response = requests.post(
            base_url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )

    except requests.RequestException as exc:

        raise RuntimeError(
            f"Capgemini connection failed: {exc}"
        ) from exc

    # ---------------------------------------------------------------
    # Errors
    # ---------------------------------------------------------------

    if response.status_code == 401:

        raise RuntimeError(
            "Capgemini authentication failed "
            "(HTTP 401). Verify the current "
            "CAPGEMINI_LLM_API_KEY."
        )

    if response.status_code >= 400:

        raise RuntimeError(
            "Capgemini request failed "
            f"HTTP {response.status_code}: "
            f"{response.text[:4000]}"
        )

    # ---------------------------------------------------------------
    # Parse response
    # ---------------------------------------------------------------

    try:

        data = response.json()

    except ValueError as exc:

        raise RuntimeError(
            "Capgemini returned a non-JSON response: "
            f"{response.text[:2000]}"
        ) from exc

    # ---------------------------------------------------------------
    # Capgemini response shown in your screenshot
    # ---------------------------------------------------------------

    text = None

    if isinstance(data, dict):

        # Direct response:
        # {
        #   "type": "text",
        #   "content": "Hello..."
        # }

        if data.get("content"):
            text = data["content"]

        # Some APIs wrap response content.
        if not text and isinstance(
            data.get("data"),
            dict,
        ):
            text = data["data"].get(
                "content"
            )

        # Fallback for OpenAI-compatible response.
        if not text:

            choices = data.get(
                "choices"
            )

            if (
                isinstance(choices, list)
                and choices
            ):

                first = choices[0]

                if isinstance(
                    first,
                    dict,
                ):

                    message = first.get(
                        "message"
                    )

                    if isinstance(
                        message,
                        dict,
                    ):
                        text = message.get(
                            "content"
                        )

    if not text:

        raise RuntimeError(
            "Capgemini returned HTTP 200, "
            "but no generated text was found "
            "in the response. Response keys: "
            f"{list(data.keys()) if isinstance(data, dict) else type(data)}"
        )

    return LLMResult(
        text=str(text).strip(),
        provider="capgemini",
        model=model,
    )


# =============================================================================
# GENERIC OPENAI-COMPATIBLE
# =============================================================================


def _chat_openai_compatible(
    messages: list[dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 1200,
) -> LLMResult:

    base_url = _secret(
        "LLM_BASE_URL"
    ).rstrip("/")

    api_key = _secret(
        "LLM_API_KEY"
    )

    model = _secret(
        "LLM_MODEL"
    )

    if not base_url:

        raise RuntimeError(
            "LLM_BASE_URL is missing."
        )

    if not api_key:

        raise RuntimeError(
            "LLM_API_KEY is missing."
        )

    if not model:

        raise RuntimeError(
            "LLM_MODEL is missing."
        )

    url = base_url

    if not url.endswith(
        "/chat/completions"
    ):

        url += "/chat/completions"

    response = requests.post(
        url,
        headers={
            "Authorization":
                f"Bearer {api_key}",
            "Content-Type":
                "application/json",
        },
        json={
            "model":
                model,
            "messages":
                messages,
            "temperature":
                temperature,
            "max_tokens":
                max_tokens,
        },
        timeout=int(
            _secret(
                "LLM_TIMEOUT_SECONDS",
                "90",
            )
        ),
    )

    if response.status_code >= 400:

        raise RuntimeError(
            "OpenAI-compatible request failed "
            f"HTTP {response.status_code}: "
            f"{response.text[:1500]}"
        )

    data = response.json()

    text = _extract_capgemini_text(
        data
    )

    return LLMResult(
        text=text,
        provider="openai_compatible",
        model=model,
    )


# =============================================================================
# PUBLIC CHAT API
# =============================================================================


def chat(
    messages: list[dict[str, str]],
    temperature: float = 0.1,
    max_tokens: int = 1200,
) -> LLMResult:
    """
    Public entry point used by Ask AI.
    """

    provider = provider_name()

    if provider == "capgemini":

        return _chat_capgemini(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider == "azure":

        return _chat_azure(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider in {
        "openai_compatible",
        "enterprise",
    }:

        return _chat_openai_compatible(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise RuntimeError(
        "No supported enterprise AI provider "
        "is configured."
    )


# =============================================================================
# JSON EXTRACTION
# =============================================================================


def extract_json(
    text: str,
):
    """
    Extract JSON returned by the LLM.
    """

    cleaned = str(
        text
    ).strip()

    cleaned = re.sub(
        r"^```(?:json)?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    cleaned = re.sub(
        r"```$",
        "",
        cleaned,
    ).strip()

    return json.loads(
        cleaned
    )
