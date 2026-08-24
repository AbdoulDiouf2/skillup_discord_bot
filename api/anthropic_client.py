import httpx

from api.config import ANTHROPIC_API_KEY

ANTHROPIC_API_BASE = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "claude-haiku-4-5-20251001"

_http: httpx.AsyncClient | None = None


class AnthropicAPIError(Exception):
    """Panne ou erreur inattendue de l'API Anthropic (réseau, timeout, quota, 5xx) —
    l'appelant décide comment le signaler, jamais de texte vide silencieux."""


def init_http_client() -> None:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(
            base_url=ANTHROPIC_API_BASE,
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            timeout=30.0,
        )


async def close_http_client() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


async def generate_bilan_suggestion(prompt: str) -> str:
    """Envoie `prompt` à Claude Haiku et retourne le texte généré — brouillon de bilan,
    jamais sauvegardé automatiquement (l'appelant/l'admin décide). Température basse et
    max_tokens modeste : un bilan hebdo/vague reste court, pas besoin de plus."""
    if _http is None:
        raise AnthropicAPIError("Client HTTP Anthropic non initialisé.")

    try:
        resp = await _http.post(
            "/messages",
            json={
                "model": MODEL,
                "max_tokens": 500,
                "temperature": 0.3,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    except httpx.HTTPError as e:
        raise AnthropicAPIError(f"Échec de connexion à l'API Anthropic : {e}") from e

    if resp.status_code >= 400:
        raise AnthropicAPIError(f"Erreur API Anthropic : {resp.status_code} {resp.text}")

    data = resp.json()
    blocks = data.get("content") or []
    texte = "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()
    if not texte:
        raise AnthropicAPIError("Réponse Anthropic vide (aucun bloc texte).")
    return texte
