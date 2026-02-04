"""OpenAI client singleton service.

Provides a shared OpenAI client instance following the same singleton
pattern as StorageService and TavilyService.
"""

import os
from dataclasses import dataclass

from openai import OpenAI


@dataclass
class OpenAIClientConfig:
    """Configuration for OpenAI client."""

    api_key: str | None = None
    timeout: float = 60.0
    max_retries: int = 2


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
