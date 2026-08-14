import json
from typing import Any, Literal

import httpx
from pydantic import BaseModel

from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.providers import ModelInfo, ProviderEndpoint
from corpussieve.models.base import CapabilityResult, ModelProvider
from corpussieve.models.config import get_auth_token
from corpussieve.models.errors import classify_httpx_error

LMSTUDIO_DEFAULT_URL = "http://127.0.0.1:1234"

# Local structured-completion calls can involve cold model loads (tens of
# seconds for large weights) in addition to generation time, so this needs
# a much longer budget than a typical network request.
REQUEST_TIMEOUT_S = 120.0


class LMStudioProvider(ModelProvider):
    """Provider implementation for local LM Studio instance (http://127.0.0.1:1234)."""

    @classmethod
    def detect(cls) -> ProviderEndpoint | None:
        """Probe default LM Studio loopback URL."""
        try:
            r = httpx.get(f"{LMSTUDIO_DEFAULT_URL}/v1/models", timeout=1.5)
            if r.status_code == 200:
                return ProviderEndpoint(
                    provider="lmstudio",
                    base_url=LMSTUDIO_DEFAULT_URL,
                    is_loopback=True,
                )
        except Exception:
            pass
        return None

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.endpoint.auth_token_ref:
            token = get_auth_token(self.endpoint.auth_token_ref)
            if token:
                headers["Authorization"] = f"Bearer {token}"
        return headers

    def health(self) -> bool:
        """Check endpoint health."""
        try:
            r = httpx.get(
                f"{self.endpoint.base_url}/v1/models",
                headers=self._get_headers(),
                timeout=3.0,
            )
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self) -> list[ModelInfo]:
        """List all available models in LM Studio instance."""
        url = f"{self.endpoint.base_url}/v1/models"
        try:
            r = httpx.get(url, headers=self._get_headers(), timeout=5.0)
            r.raise_for_status()
            data = r.json()
            models: list[ModelInfo] = []
            for item in data.get("data", []):
                mid = item.get("id", "")
                mtype = item.get("type", "chat")
                # Filter embedding models if typed
                if "embed" in mid.lower() or mtype == "embedding":
                    continue
                models.append(
                    ModelInfo(
                        provider="lmstudio",
                        model_id=mid,
                        loaded=True,
                        model_type="chat",
                        capability_result="untested",
                    )
                )
            return models
        except Exception as e:
            raise classify_httpx_error(e, "LM Studio", self.endpoint.base_url) from e

    def loaded_models(self) -> list[ModelInfo]:
        """List currently loaded active models in LM Studio."""
        return self.list_models()

    def capability_test(self, model_id: str) -> CapabilityResult:
        """Run standard capability test."""

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
                provider="lmstudio",
                model_id=model_id,
                status="passed",
                score="3/3",
                details=["Passed standard capability test"],
            )
        except Exception as e:
            return CapabilityResult(
                provider="lmstudio",
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
        """Request structured completion matching schema from LM Studio chat completions API."""
        url = f"{self.endpoint.base_url}/v1/chat/completions"
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
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__,
                        "strict": True,
                        "schema": json_schema,
                    },
                },
                "temperature": 0,
            }

            try:
                r = httpx.post(
                    url, headers=self._get_headers(), json=payload, timeout=REQUEST_TIMEOUT_S
                )
                r.raise_for_status()
                res_json = r.json()
                content_str = res_json.get("choices", [{}])[0].get("message", {}).get("content", "")

                data = json.loads(content_str)
                return schema.model_validate(data)

            except httpx.TimeoutException as err:
                # Retrying won't make a slow/loading model faster; fail fast
                # instead of burning max_retries * REQUEST_TIMEOUT_S.
                raise CorpusSieveError(
                    ErrorCode.MODEL_SCHEMA_TEST_FAILED,
                    f"LM Studio request to model '{model_id}' timed out after "
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

        msg = f"LM Studio completion failed after {max_retries + 1} attempts: {last_error}"
        raise CorpusSieveError(
            ErrorCode.MODEL_SCHEMA_TEST_FAILED,
            msg,
            detail={"model_id": model_id, "error": last_error},
        )

    def provider_metadata(self) -> dict[str, Any]:
        """Return metadata for LM Studio provider."""
        return {
            "provider": "lmstudio",
            "base_url": self.endpoint.base_url,
            "is_loopback": self.endpoint.is_loopback,
        }
