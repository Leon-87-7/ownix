"""Central Gemini text-generation client — free→paid key fallback."""
from __future__ import annotations

import asyncio

from src.config import settings
from src.utils.logger import get_logger

log = get_logger(__name__)


class GeminiUnavailableError(Exception):
    """Raised when both free and paid Gemini keys fail."""


class GeminiClient:
    async def generate(
        self,
        prompt: str,
        *,
        model: str,
        schema: type | dict | None = None,
    ) -> str:
        """Generate text via Gemini. Tries GEMINI_FREE_API_KEY then GEMINI_PAID_API_KEY.

        Raises GeminiUnavailableError when both keys fail.
        """
        last_error: str | None = None
        for key in [settings.GEMINI_FREE_API_KEY, settings.GEMINI_PAID_API_KEY]:
            if not key:
                continue
            try:
                result = await asyncio.to_thread(
                    self._call_sync, prompt, key, model, schema
                )
                log.info("gemini_client.generate_ok", model=model)
                return result
            except Exception as exc:
                last_error = str(exc).splitlines()[0][:120]
                log.warning("gemini_client.key_failed", model=model, error=last_error)
        raise GeminiUnavailableError(last_error or "Both Gemini keys failed")

    @staticmethod
    def _call_sync(
        prompt: str, api_key: str, model: str, schema: type | dict | None
    ) -> str:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        if schema is not None:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
            )
            response = client.models.generate_content(
                model=model, contents=prompt, config=config
            )
        else:
            response = client.models.generate_content(model=model, contents=prompt)
        return response.text or ""


gemini_client = GeminiClient()
