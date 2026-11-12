from __future__ import annotations

import re

from pydantic import BaseModel, EmailStr, Field, field_validator

_HTML_CHARS = re.compile(r"[<>\"'&]")


def plain_text(value: str) -> str:
    """Names are shown in HTML by every client; keep them free of markup characters."""
    return _HTML_CHARS.sub("", value).strip()



class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        return plain_text(v)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    plan: str
    credits: int
    is_admin: bool
    api_key: str
    plan_info: dict


class VoiceOut(BaseModel):
    id: str
    name: str
    language: str
    engine: str
    description: str
    created_at: str


class TTSIn(BaseModel):
    voice_id: str
    text: str = Field(min_length=1, max_length=5000)
    translate_to: str | None = None
    source_lang: str = "auto"


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    target: str
    source: str = "auto"


class JobOut(BaseModel):
    id: str
    kind: str
    status: str
    progress: float
    message: str
    params: dict
    output_url: str | None
    credits_cost: int
    created_at: str


class PlanChangeIn(BaseModel):
    plan: str


class AdminCreditsIn(BaseModel):
    user_email: EmailStr
    delta: int
    reason: str = "manual"
