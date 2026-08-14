from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from corpussieve.contracts.providers import ModelInfo, ProviderEndpoint


class CapabilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    model_id: str
    status: Literal["passed", "warn", "failed"]
    score: str
    details: list[str] = Field(default_factory=list)


class ModelProvider(ABC):
    """Abstract Base Class for AI Model Providers (Ollama, LM Studio)."""

    def __init__(self, endpoint: ProviderEndpoint) -> None:
        self.endpoint = endpoint

    @classmethod
    @abstractmethod
    def detect(cls) -> ProviderEndpoint | None:
        """Probe default loopback URL (timeout 1.5s). Return endpoint if reachable."""

    @abstractmethod
    def health(self) -> bool:
        """Return True if provider API endpoint is healthy."""

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """Return list of available models."""

    @abstractmethod
    def loaded_models(self) -> list[ModelInfo]:
        """Return list of currently loaded models."""

    @abstractmethod
    def capability_test(self, model_id: str) -> CapabilityResult:
        """Run structured output capability test on model."""

    @abstractmethod
    def complete_structured(
        self,
        model_id: str,
        schema: type[BaseModel],
        system: str,
        prompt: str,
        max_retries: int = 2,
    ) -> BaseModel:
        """Request structured JSON completion adhering to schema."""

    @abstractmethod
    def provider_metadata(self) -> dict[str, Any]:
        """Return provider metadata dictionary."""
