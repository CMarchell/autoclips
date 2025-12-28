"""LLM interface for AI text generation."""

from typing import Optional

from ..core.config import settings


def call_llm(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.8,
    max_tokens: int = 2000,
    provider: Optional[str] = None,
) -> str:
    """Call the configured LLM provider.

    Args:
        prompt: The user prompt
        system_prompt: Optional system prompt
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        provider: Override the default provider ('anthropic' or 'openai')

    Returns:
        Generated text response
    """
    provider = provider or settings.ai_provider or settings.ai.default_provider

    if provider == "anthropic":
        return _call_anthropic(prompt, system_prompt, temperature, max_tokens)
    elif provider == "openai":
        return _call_openai(prompt, system_prompt, temperature, max_tokens)
    else:
        raise ValueError(f"Unknown AI provider: {provider}")


def _call_anthropic(
    prompt: str,
    system_prompt: Optional[str],
    temperature: float,
    max_tokens: int,
) -> str:
    """Call Anthropic's Claude API."""
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    kwargs = {
        "model": settings.ai.anthropic_model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }

    if system_prompt:
        kwargs["system"] = system_prompt

    response = client.messages.create(**kwargs)
    return response.content[0].text


def _call_openai(
    prompt: str,
    system_prompt: Optional[str],
    temperature: float,
    max_tokens: int,
) -> str:
    """Call OpenAI's GPT API."""
    import openai

    client = openai.OpenAI(api_key=settings.openai_api_key)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=settings.ai.openai_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content
