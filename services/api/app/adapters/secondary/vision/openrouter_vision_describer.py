"""Vision describer via OpenRouter (Chat Completions API com image_url base64).

Implementa :class:`VisionDescriber`. Chamada síncrona com timeout configurável
para que o upload do utilizador receba a descrição em ~3-8 segundos no caminho
mais comum (gpt-4o-mini é rápido e barato).

Falha controlada: se a API retornar erro ou timeout, devolve uma descrição
mínima sintética para que o fluxo de chat não quebre — o agente saberá
apenas que "uma imagem foi anexada (descrição indisponível)".
"""

from __future__ import annotations

import base64
import logging

import httpx

from app.ports.services import VisionDescriber

log = logging.getLogger(__name__)


_DEFAULT_PROMPT = (
    "Descreva esta imagem em detalhe técnico para um agente de IA "
    "raciocinar sobre ela como texto. Cite, na seguinte ordem:\n"
    "1. Tipo de imagem (screenshot, diagrama, foto, mapa mental, gráfico, etc.).\n"
    "2. Hierarquia e estrutura visual (nó central, ramos, colunas, secções).\n"
    "3. Texto visível, palavra por palavra (preserve maiúsculas e símbolos).\n"
    "4. Cores, ícones, conexões/setas e relações entre elementos.\n"
    "5. Qualquer dado numérico, código ou métrica.\n"
    "Seja exaustivo. O agente NÃO verá a imagem — só o seu texto."
)


class OpenRouterVisionDescriber(VisionDescriber):
    """Chama um modelo multimodal (default ``openai/gpt-4o-mini``) via OpenRouter."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
        model: str = "openai/gpt-4o-mini",
        max_tokens: int = 800,
        timeout_s: int = 60,
    ) -> None:
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self._model = model
        self._max_tokens = max_tokens
        self._timeout = timeout_s

    async def describe(
        self, *, mime_type: str, content: bytes, hint: str | None = None
    ) -> tuple[str, str]:
        if not self._api_key:
            log.warning("vision_provider_api_key vazia — descrição mínima.")
            return self._fallback("API key de visão não configurada"), self._model

        b64 = base64.b64encode(content).decode("ascii")
        data_url = f"data:{mime_type};base64,{b64}"
        prompt = _DEFAULT_PROMPT
        if hint:
            prompt += f"\n\nContexto adicional do utilizador: {hint}"

        payload = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base}/chat/completions",
                    json=payload,
                    headers=headers,
                )
            if resp.status_code != 200:
                log.warning(
                    "vision describer HTTP %s: %s",
                    resp.status_code,
                    resp.text[:200],
                )
                return (
                    self._fallback(f"vision API HTTP {resp.status_code}"),
                    self._model,
                )
            body = resp.json()
            text = body.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if not text:
                return (
                    self._fallback("vision API devolveu corpo vazio"),
                    self._model,
                )
            return text, self._model
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            log.exception("vision describer falhou: %s", exc)
            return self._fallback(f"erro: {exc}"), self._model

    @staticmethod
    def _fallback(reason: str) -> str:
        return (
            f"[Imagem anexada — descrição automática indisponível ({reason}). "
            "O agente sabe que existe um anexo, mas não viu o conteúdo.]"
        )
