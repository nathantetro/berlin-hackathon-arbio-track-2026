"""OpenAI client singleton service.

Provides a shared OpenAI client instance following the same singleton
pattern as StorageService and TavilyService.
"""

import os
from dataclasses import dataclass

from openai import OpenAI, RateLimitError, APITimeoutError, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_random_exponential, retry_if_exception_type


@dataclass
class OpenAIClientConfig:
    """Configuration for OpenAI client."""

    api_key: str | None = None
    timeout: float = 60.0
    max_retries: int = 5


# Singleton instance
_openai_client: OpenAI | None = None


def get_openai_client(config: OpenAIClientConfig | None = None) -> OpenAI:
    """Get the singleton OpenAI client instance.

    Args:
        config: Optional configuration. If not provided, uses defaults
                (reads OPENAI_API_KEY from environment).

    Returns:
        Shared OpenAI client instance.
    """
    global _openai_client
    if _openai_client is None:
        if config is None:
            # Default configuration
            _openai_client = OpenAI()
        else:
            # Custom configuration
            api_key = config.api_key or os.getenv("OPENAI_API_KEY")
            _openai_client = OpenAI(
                api_key=api_key,
                timeout=config.timeout,
                max_retries=config.max_retries,
            )
    return _openai_client


def reset_openai_client() -> None:
    """Reset the singleton OpenAI client instance.

    This is primarily useful for testing to ensure a fresh client
    with new configuration.
    """
    global _openai_client
    _openai_client = None


@retry(
    wait=wait_random_exponential(min=1, max=60),
    stop=stop_after_attempt(6),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
)
def chat_completion_with_backoff(client: OpenAI, **kwargs):
    """Chat completion with exponential backoff for rate limits.

    Wraps client.chat.completions.create() with tenacity retry logic.
    Retries on rate limit (429), timeout, and connection errors with
    random exponential backoff (1-60 seconds, up to 6 attempts).

    Args:
        client: OpenAI client instance
        **kwargs: Arguments passed to chat.completions.create()

    Returns:
        ChatCompletion response from OpenAI API
    """
    return client.chat.completions.create(**kwargs)
