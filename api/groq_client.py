import httpx

from api.config import GROQ_API_KEY

GROQ_API_BASE = "https://api.groq.com/openai/v1"

_http: httpx.AsyncClient | None = None


class GroqAPIError(Exception):
    """Panne ou erreur inattendue de l'API Groq (réseau, timeout, quota, 5xx, clé
    absente) — même convention que AnthropicAPIError."""


def init_http_client() -> None:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(
            base_url=GROQ_API_BASE,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY or ''}",
                "content-type": "application/json",
            },
            timeout=30.0,
        )


async def close_http_client() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


async def list_models() -> list[str]:
    """Modèles Groq disponibles pour cette clé — GET /openai/v1/models. Évite de figer
    une liste en dur côté code (catalogue Groq qui change/déprécie souvent)."""
    if not GROQ_API_KEY:
        raise GroqAPIError("GROQ_API_KEY absente du .env — provider Groq indisponible.")
    if _http is None:
        raise GroqAPIError("Client HTTP Groq non initialisé.")

    try:
        resp = await _http.get("/models")
    except httpx.HTTPError as e:
        raise GroqAPIError(f"Échec de connexion à l'API Groq : {e}") from e

    if resp.status_code >= 400:
        raise GroqAPIError(f"Erreur API Groq : {resp.status_code} {resp.text}")

    data = resp.json()
    return [m["id"] for m in data.get("data", [])]


async def generate(prompt: str, model: str) -> str:
    """Envoie `prompt` au modèle Groq `model` (API compatible OpenAI Chat Completions)
    et retourne le texte généré. Même contrat que anthropic_client.generate."""
    if not GROQ_API_KEY:
        raise GroqAPIError("GROQ_API_KEY absente du .env — provider Groq indisponible.")
    if _http is None:
        raise GroqAPIError("Client HTTP Groq non initialisé.")

    try:
        resp = await _http.post(
            "/chat/completions",
            json={
                "model": model,
                "max_tokens": 500,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    except httpx.HTTPError as e:
        raise GroqAPIError(f"Échec de connexion à l'API Groq : {e}") from e

    if resp.status_code >= 400:
        raise GroqAPIError(f"Erreur API Groq : {resp.status_code} {resp.text}")

    data = resp.json()
    choices = data.get("choices") or []
    texte = (choices[0].get("message", {}).get("content") or "").strip() if choices else ""
    if not texte:
        raise GroqAPIError("Réponse Groq vide.")
    return texte
