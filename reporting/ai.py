"""Optional hosted interpretation; SQL and application validation remain authoritative."""

import json
import re

import httpx

from .settings import settings


class AIUnavailable(ValueError):
    pass


def structured(instruction, payload, schema):
    if not settings.gemini_api_key:
        raise AIUnavailable(
            "AI is not configured. Use the local/manual option or configure the backend key."
        )
    if not re.fullmatch(r"[a-zA-Z0-9.-]{1,100}", settings.gemini_model):
        raise AIUnavailable("Invalid configured model identifier")
    try:
        with httpx.Client(timeout=20) as client:
            response = client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
                headers={"x-goog-api-key": settings.gemini_api_key},
                json={
                    "systemInstruction": {"parts": [{"text": instruction}]},
                    "contents": [
                        {"role": "user", "parts": [{"text": json.dumps(payload)}]}
                    ],
                    "generationConfig": {
                        "temperature": 0,
                        "maxOutputTokens": 1500,
                        "responseMimeType": "application/json",
                        "responseJsonSchema": schema,
                    },
                },
            )
        response.raise_for_status()
        parts = response.json()["candidates"][0]["content"]["parts"]
        if not isinstance(parts, list) or not all(isinstance(p, dict) for p in parts):
            raise TypeError("Invalid response parts")
        value = json.loads("".join(p.get("text", "") for p in parts))
        if not isinstance(value, dict):
            raise TypeError("Expected object")
        return value
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        # Never return provider response bodies or credentials to browser/logs.
        raise AIUnavailable(
            "AI service unavailable or returned an invalid response. Manual/local tools still work."
        ) from exc
