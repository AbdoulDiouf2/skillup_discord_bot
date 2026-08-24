from api import anthropic_client, groq_client

PROVIDERS = ("anthropic", "groq")


class AIProviderError(Exception):
    """Enveloppe AnthropicAPIError/GroqAPIError sous un type unique côté routeur —
    peu importe le provider configuré, l'appelant gère une seule exception."""


async def generate_suggestion(provider: str, model: str, prompt: str) -> str:
    if provider == "anthropic":
        try:
            return await anthropic_client.generate(prompt, model)
        except anthropic_client.AnthropicAPIError as e:
            raise AIProviderError(str(e)) from e
    if provider == "groq":
        try:
            return await groq_client.generate(prompt, model)
        except groq_client.GroqAPIError as e:
            raise AIProviderError(str(e)) from e
    raise AIProviderError(f"Provider IA inconnu : {provider!r}.")
