"""Free offline translation with NLLB-200 (Egyptian Arabic `arz` is a real language there)."""
from __future__ import annotations

import threading

from ..config import MOCK

CODES = {"ar-EG": "arz_Arab", "ar": "arb_Arab", "en": "eng_Latn", "fr": "fra_Latn", "de": "deu_Latn",
         "es": "spa_Latn", "it": "ita_Latn", "pt": "por_Latn", "tr": "tur_Latn", "ru": "rus_Cyrl",
         "hi": "hin_Deva", "zh": "zho_Hans", "ja": "jpn_Jpan", "ko": "kor_Hang", "nl": "nld_Latn",
         "pl": "pol_Latn", "sv": "swe_Latn", "el": "ell_Grek", "he": "heb_Hebr", "ms": "zsm_Latn",
         "sw": "swh_Latn", "da": "dan_Latn", "fi": "fin_Latn", "no": "nob_Latn"}
MODEL = "facebook/nllb-200-distilled-600M"

_lock = threading.Lock()
_pipe = None


def available() -> bool:
    import importlib.util
    return MOCK or importlib.util.find_spec("transformers") is not None


def translate(text: str, src: str, tgt: str) -> str:
    if src == tgt:
        return text
    if MOCK:
        return f"[{tgt}] {text}"
    if src not in CODES or tgt not in CODES:
        raise LookupError(f"لغة غير مدعومة: {src} → {tgt}")
    global _pipe
    with _lock:
        if _pipe is None:
            from transformers import pipeline
            _pipe = pipeline("translation", model=MODEL)
        return _pipe(text, src_lang=CODES[src], tgt_lang=CODES[tgt], max_length=1024)[0]["translation_text"]
