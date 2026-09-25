"""
LLM provider abstraction — OpenAI-compatible interface.

Swap providers by changing .env only.

``create_completion`` is the single retried seam used by ``router.route_chat``.
The ``_chat_completion`` / ``_chat_completion_with_tools`` helpers are PRIVATE
seams (legacy + live-smoke-test only): callers that need usage accounting and
budget enforcement MUST route through ``ai.engine.llm.router.route_chat``.
"""
import logging
from dataclasses import dataclass

from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    RateLimitError,
)
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from ai.engine.core.config import get_settings

logger = logging.getLogger("pulse.llm.provider")

RETRYABLE_ERRORS = (APITimeoutError, RateLimitError, APIConnectionError, InternalServerError)

_retry_decorator = retry(
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    stop=stop_after_attempt(4),
    wait=wait_random_exponential(multiplier=1, max=10),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def classify_llm_error(exc: Exception) -> str:
    """Classify an LLM failure as ``transient`` (retryable) or ``permanent``.

    Lets the frontend distinguish "tap to retry" (transient) from a
    definitive offline/configuration state (permanent) without parsing
    provider error strings.
    """
    if isinstance(exc, RETRYABLE_ERRORS):
        return "transient"
    return "permanent"


def _is_deepseek_endpoint(base_url: str | None = None) -> bool:
    """True when the configured LLM endpoint is DeepSeek's OpenAI-compatible API."""
    url = (base_url if base_url is not None else get_settings().LLM_BASE_URL) or ""
    return "deepseek.com" in url.lower()


@dataclass(frozen=True)
class ReasoningMode:
    """How one provider returns a reasoning trace in ``reasoning_content``.

    ``forced_tool``: the provider accepts a named or required tool_choice
    while reasoning. Anthropic models reject that pair with a 400.
    ``temperature``: the sampling temperature the provider requires while
    reasoning, or None when any is accepted.
    """

    body: dict
    forced_tool: bool
    temperature: float | None = None


def _is_anthropic_model(model: str | None) -> bool:
    name = str(model or "").strip().lower()
    return name.startswith("anthropic/") or "claude" in name


def reasoning_mode(model: str | None, base_url: str | None = None) -> ReasoningMode | None:
    """The declared reasoning request for this model, or None when it has none."""
    if _is_deepseek_endpoint(base_url):
        return ReasoningMode(body={"thinking": {"type": "enabled"}}, forced_tool=False)
    if _is_anthropic_model(model):
        return ReasoningMode(body={"reasoning_effort": "low"}, forced_tool=False, temperature=1.0)
    return None


def _apply_provider_kwargs(kwargs: dict) -> dict:
    """Normalize provider-specific kwargs before the chat.completions call.

    DeepSeek V4.1 enables *thinking* by default. That mode returns long
    ``reasoning_content`` streams, often empty ``content`` on tool-call turns,
    and routinely exceeds the old 30s client timeout — which made Pulse look
    stuck ("working… then nothing") when Gunicorn killed the worker.

    Disable thinking unless the caller explicitly set ``extra_body.thinking``.
    """
    out = dict(kwargs)
    if not _is_deepseek_endpoint():
        return out
    extra = dict(out.get("extra_body") or {})
    if "thinking" not in extra:
        extra["thinking"] = {"type": "disabled"}
    out["extra_body"] = extra
    return out


@_retry_decorator
async def create_completion(client: AsyncOpenAI, **kwargs):
    """Create a completion with retry on transient errors.

    The single retried seam used by ``router.route_chat`` — the user-facing
    chat path previously bypassed retry by calling the raw client directly.
    """
    return await client.chat.completions.create(**_apply_provider_kwargs(kwargs))


def _openai_client(api_key: str, base_url: str) -> AsyncOpenAI:
    timeout = 120.0 if _is_deepseek_endpoint(base_url) else 30.0
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_retries=0,
    )


def get_llm_client() -> AsyncOpenAI:
    """Create an AsyncOpenAI client from settings."""
    settings = get_settings()
    # DeepSeek thinking (when re-enabled) and tool loops need headroom;
    # 30s caused APITimeoutError → retries → gunicorn WORKER TIMEOUT.
    return _openai_client(settings.LLM_API_KEY, settings.LLM_BASE_URL)


def client_for_model(model: str | None) -> tuple[AsyncOpenAI, str, str]:
    """Return ``(client, wire model, base url)`` for this model id.

    A deepseek id uses the direct DeepSeek key when one is configured.
    Anything else stays on the primary provider.
    """
    settings = get_settings()
    name = (model or "").strip()
    low = name.lower()
    key = (settings.DEEPSEEK_API_KEY or "").strip()
    if key and "deepseek" in low:
        wire = "deepseek-flash" if "pro" not in low else "deepseek-v4-pro"
        base = (settings.DEEPSEEK_BASE_URL or "https://api.deepseek.com/v1").strip()
        return _openai_client(key, base), wire, base
    return get_llm_client(), name, settings.LLM_BASE_URL


@_retry_decorator
async def _chat_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.3,
    response_format: dict | None = None,
) -> str:
    """Simple wrapper: send messages, return assistant response text.

    Retries on timeout, rate limit, connection error, and 5xx
    (up to 3 attempts with exponential backoff 1s/2s/4s).
    Non-retryable errors (auth, bad request) fail immediately.
    """
    settings = get_settings()
    client = get_llm_client()
    model = model or settings.LLM_MODEL
    logger.debug(f"_chat_completion: model={model}  messages={len(messages)}")

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format

    response = await client.chat.completions.create(**_apply_provider_kwargs(kwargs))
    text = response.choices[0].message.content
    logger.debug(f"_chat_completion done: {len(text or '')} chars")
    return text


@_retry_decorator
async def _chat_completion_with_tools(
    messages: list[dict],
    tools: list[dict],
    model: str | None = None,
    temperature: float = 0.3,
    response_format: dict | None = None,
) -> dict:
    """Send messages with tool definitions, return full response including tool calls.

    Retries on timeout, rate limit, connection error, and 5xx
    (up to 3 attempts with exponential backoff 1s/2s/4s).
    Non-retryable errors (auth, bad request) fail immediately.
    """
    settings = get_settings()
    client = get_llm_client()
    model = model or settings.LLM_MODEL

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "tools": tools,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format

    response = await client.chat.completions.create(**_apply_provider_kwargs(kwargs))
    choice = response.choices[0]
    result = {
        "content": choice.message.content,
        "tool_calls": None,
        "finish_reason": choice.finish_reason,
    }
    if choice.message.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                },
            }
            for tc in choice.message.tool_calls
        ]
    return result
