"""
LLM provider abstraction — OpenAI-compatible interface.
Swap providers by changing .env only.
"""
import logging

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
    wait_exponential,
)

from ai.engine.core.config import get_settings

logger = logging.getLogger("pulse.llm.provider")

RETRYABLE_ERRORS = (APITimeoutError, RateLimitError, APIConnectionError, InternalServerError)

_retry_decorator = retry(
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
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


@_retry_decorator
async def create_completion(client: AsyncOpenAI, **kwargs):
    """Create a completion with retry on transient errors.

    The single retried seam used by ``router.route_chat`` — the user-facing
    chat path previously bypassed retry by calling the raw client directly.
    """
    return await client.chat.completions.create(**kwargs)


def get_llm_client() -> AsyncOpenAI:
    """Create an AsyncOpenAI client from settings."""
    settings = get_settings()
    return AsyncOpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        timeout=30.0,
        max_retries=0,
    )


@_retry_decorator
async def chat_completion(
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
    logger.debug(f"chat_completion: model={model}  messages={len(messages)}")

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format

    response = await client.chat.completions.create(**kwargs)
    text = response.choices[0].message.content
    logger.debug(f"chat_completion done: {len(text or '')} chars")
    return text


@_retry_decorator
async def chat_completion_with_tools(
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

    response = await client.chat.completions.create(**kwargs)
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
