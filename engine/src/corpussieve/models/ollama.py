import json
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.providers import ModelInfo, ProviderEndpoint
from corpussieve.models.base import CapabilityResult, ModelProvider
from corpussieve.models.errors import classify_httpx_error

OLLAMA_DEFAULT_URL = "http://127.0.0.1:11434"

# Local structured-completion calls can involve cold model loads (tens of
# seconds for large weights) in addition to generation time, so this needs
# a much longer budget than a typical network request.
REQUEST_TIMEOUT_S = 120.0


class OllamaProvider(ModelProvider):
    """Provider implementation for local Ollama instance (http://127.0.0.1:11434)."""

    @classmethod
    def detect(cls) -> ProviderEndpoint | None:
        """Probe default Ollama loopback URL."""
        try:
            r = httpx.get(f"{OLLAMA_DEFAULT_URL}/api/tags", timeout=1.5)
            if r.status_code == 200:
                return ProviderEndpoint(
                    provider="ollama",
                    base_url=OLLAMA_DEFAULT_URL,
                    is_loopback=True,
                )
        except Exception:
            pass
        return None

    def health(self) -> bool:
        """Check endpoint health."""
        try:
            r = httpx.get(f"{self.endpoint.base_url}/api/tags", timeout=3.0)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[ModelInfo]:
        """List all available models in Ollama instance."""
        url = f"{self.endpoint.base_url}/api/tags"
        try:
            r = httpx.get(url, timeout=5.0)
            r.raise_for_status()
            data = r.json()
            models: list[ModelInfo] = []
            for item in data.get("models", []):
                name = item.get("name", "")
                details = item.get("details", {})
                family = details.get("family", "")
                models.append(
                    ModelInfo(
                        provider="ollama",
                        model_id=name,
                        loaded=False,
                        model_type=family or "chat",
                        context_length=item.get("context_length"),
                        capability_result="untested",
                    )
                )
            return models
        except Exception as e:
            raise classify_httpx_error(e, "Ollama", self.endpoint.base_url) from e

    def loaded_models(self) -> list[ModelInfo]:
        """List currently loaded active models in VRAM."""
        url = f"{self.endpoint.base_url}/api/ps"
        try:
            r = httpx.get(url, timeout=5.0)
            r.raise_for_status()
            data = r.json()
            models: list[ModelInfo] = []
            for item in data.get("models", []):
                name = item.get("name", "")
                models.append(
                    ModelInfo(
                        provider="ollama",
                        model_id=name,
                        loaded=True,
                        model_type="chat",
                        capability_result="untested",
                    )
                )
            return models
        except Exception as e:
            raise classify_httpx_error(e, "Ollama", self.endpoint.base_url) from e

    def capability_test(self, model_id: str) -> CapabilityResult:
        """Run standard capability test."""

        # Simple test prompt
        class SimpleTest(BaseModel):
            decision: Literal["include", "exclude"]

        try:
            self.complete_structured(
                model_id=model_id,
                schema=SimpleTest,
                system="Respond in JSON.",
                prompt="Include video games?",
            )
            return CapabilityResult(
                provider="ollama",
                model_id=model_id,
                status="passed",
                score="3/3",
                details=["Passed standard capability test"],
            )
        except Exception as e:
            return CapabilityResult(
                provider="ollama",
                model_id=model_id,
                status="failed",
                score="0/3",
                details=[str(e)],
            )

    def complete_structured(
        self,
        model_id: str,
        schema: type[BaseModel],
        system: str,
        prompt: str,
        max_retries: int = 2,
    ) -> BaseModel:
        """Request structured completion matching schema from Ollama chat API."""
        url = f"{self.endpoint.base_url}/api/chat"
        json_schema = schema.model_json_schema()

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]

        attempt = 0
        last_error = ""

        while attempt <= max_retries:
            payload = {
                "model": model_id,
                "messages": messages,
                "format": json_schema,
                "stream": False,
                "options": {"temperature": 0},
            }

            try:
                r = httpx.post(url, json=payload, timeout=REQUEST_TIMEOUT_S)
                r.raise_for_status()
                res_json = r.json()
                content_str = res_json.get("message", {}).get("content", "")

                data = json.loads(content_str)
                return schema.model_validate(data)

            except httpx.TimeoutException as err:
                # Retrying won't make a slow/loading model faster; fail fast
                # instead of burning max_retries * REQUEST_TIMEOUT_S.
                raise CorpusSieveError(
                    ErrorCode.MODEL_SCHEMA_TEST_FAILED,
                    f"Ollama request to model '{model_id}' timed out after "
                    f"{REQUEST_TIMEOUT_S:.0f}s. The model may still be loading, "
                    "too slow for this machine, or overloaded.",
                    detail={"model_id": model_id, "timeout_s": REQUEST_TIMEOUT_S},
                ) from err

            except (json.JSONDecodeError, ValueError, Exception) as err:
                last_error = str(err)
                attempt += 1
                if attempt <= max_retries:
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Validation failed ({err}). Output valid JSON.",
                        }
                    )

        raise CorpusSieveError(
            ErrorCode.MODEL_SCHEMA_TEST_FAILED,
            f"Ollama structured completion failed after {max_retries + 1} attempts: {last_error}",
            detail={"model_id": model_id, "error": last_error},
        )

    def provider_metadata(self) -> dict[str, Any]:
        """Return metadata for Ollama provider."""
        return {
            "provider": "ollama",
            "base_url": self.endpoint.base_url,
            "is_loopback": self.endpoint.is_loopback,
        }
