"""Script translation with Claude. Keeps the creator's tone, adapts idioms per market and
returns clean text ready for TTS (no markdown, no notes). Needs ANTHROPIC_API_KEY."""
from __future__ import annotations

import os

from . import LANGUAGES

MODEL = os.getenv("TRANSLATE_MODEL", "claude-opus-5-5")

SYSTEM = (
    "You translate short-form video scripts for a content creator whose videos are voiced with "
    "their own cloned voice. Translate faithfully but naturally for native speakers of the target "
    "language, keep the energy, rhythm and sentence length suitable for spoken delivery, keep "
    "names and brand names unchanged, write numbers as words when that sounds more natural when "
    "spoken, and never add explanations. For Egyptian Arabic, use natural everyday Egyptian "
    "dialect, not Modern Standard Arabic. Output ONLY the translated script text."
)


class ClaudeTranslator:
    name = "claude"

    def __init__(self) -> None:
        self._client = None

    def _c(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as e:
                raise RuntimeError("pip install anthropic") from e
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise RuntimeError("الترجمة تحتاج ANTHROPIC_API_KEY في ملف .env")
            self._client = anthropic.Anthropic()
        return self._client

    def translate(self, text: str, target: str, source: str = "auto") -> str:
        target_name = LANGUAGES.get(target, target)
        src = "" if source == "auto" else f" (source language: {LANGUAGES.get(source, source)})"
        response = self._c().beta.messages.create(
            model=MODEL,
            max_tokens=4096,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=SYSTEM,
            messages=[{"role": "user",
                       "content": f"Translate this script to {target_name}{src}:\n\n{text}"}],
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("تعذرت الترجمة لهذا النص")
        return "".join(b.text for b in response.content if b.type == "text").strip()
