from typing import Literal

from pydantic import BaseModel, ConfigDict


class ModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model_id: str
    loaded: bool
    model_type: str | None = None
    context_length: int | None = None
    capability_result: Literal["passed", "warn", "failed", "untested"]


class ProviderEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["ollama", "lmstudio"]
    base_url: str
    is_loopback: bool
    auth_token_ref: str | None = None
