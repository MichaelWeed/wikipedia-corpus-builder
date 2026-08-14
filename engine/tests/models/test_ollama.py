import json
from typing import Literal

import httpx
import pytest
import respx
from pydantic import BaseModel

from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.providers import ProviderEndpoint
from corpussieve.models.ollama import OLLAMA_DEFAULT_URL, OllamaProvider


class DummySchema(BaseModel):
    decision: Literal["include", "exclude"]
    reason: str


def test_ollama_detect_success(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(f"{OLLAMA_DEFAULT_URL}/api/tags").respond(
        status_code=200, json={"models": [{"name": "llama3:latest"}]}
    )

    ep = OllamaProvider.detect()
    assert ep is not None
    assert ep.provider == "ollama"
    assert ep.base_url == OLLAMA_DEFAULT_URL


def test_ollama_list_and_loaded_models(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(f"{OLLAMA_DEFAULT_URL}/api/tags").respond(
        status_code=200,
        json={
            "models": [
                {
                    "name": "llama3:latest",
                    "details": {"family": "llama", "parameter_size": "8B"},
                }
            ]
        },
    )
    respx_mock.get(f"{OLLAMA_DEFAULT_URL}/api/ps").respond(
        status_code=200,
        json={"models": [{"name": "llama3:latest"}]},
    )

    ep = ProviderEndpoint(provider="ollama", base_url=OLLAMA_DEFAULT_URL, is_loopback=True)
    provider = OllamaProvider(ep)

    models = provider.list_models()
    assert len(models) == 1
    assert models[0].model_id == "llama3:latest"

    loaded = provider.loaded_models()
    assert len(loaded) == 1
    assert loaded[0].loaded is True


def test_ollama_complete_structured_happy_path(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.post(f"{OLLAMA_DEFAULT_URL}/api/chat").respond(
        status_code=200,
        json={
            "message": {
                "content": json.dumps({"decision": "include", "reason": "Relevant category"})
            }
        },
    )

    ep = ProviderEndpoint(provider="ollama", base_url=OLLAMA_DEFAULT_URL, is_loopback=True)
    provider = OllamaProvider(ep)

    res = provider.complete_structured(
        model_id="llama3:latest",
        schema=DummySchema,
        system="System prompt",
        prompt="User prompt",
    )
    assert isinstance(res, DummySchema)
    assert res.decision == "include"
    assert res.reason == "Relevant category"


def test_ollama_auth_failed_error(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(f"{OLLAMA_DEFAULT_URL}/api/tags").respond(status_code=401)

    ep = ProviderEndpoint(provider="ollama", base_url=OLLAMA_DEFAULT_URL, is_loopback=True)
    provider = OllamaProvider(ep)

    with pytest.raises(CorpusSieveError) as exc_info:
        provider.list_models()
    assert exc_info.value.code == ErrorCode.MODEL_AUTH_FAILED


def test_ollama_complete_structured_timeout_fails_fast(
    respx_mock: respx.MockRouter,
) -> None:
    """A slow/loading model should fail with one clear error, not burn every retry."""
    call_count = 0

    def _raise_timeout(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        raise httpx.ReadTimeout("timed out", request=request)

    respx_mock.post(f"{OLLAMA_DEFAULT_URL}/api/chat").mock(side_effect=_raise_timeout)

    ep = ProviderEndpoint(provider="ollama", base_url=OLLAMA_DEFAULT_URL, is_loopback=True)
    provider = OllamaProvider(ep)

    with pytest.raises(CorpusSieveError) as exc_info:
        provider.complete_structured(
            model_id="llama3:latest",
            schema=DummySchema,
            system="System",
            prompt="User",
            max_retries=2,
        )
    assert exc_info.value.code == ErrorCode.MODEL_SCHEMA_TEST_FAILED
    assert "timed out" in exc_info.value.message
    assert call_count == 1


def test_ollama_schema_failure_retry(respx_mock: respx.MockRouter) -> None:
    respx_mock.post(f"{OLLAMA_DEFAULT_URL}/api/chat").respond(
        status_code=200,
        json={"message": {"content": "invalid json format"}},
    )

    ep = ProviderEndpoint(provider="ollama", base_url=OLLAMA_DEFAULT_URL, is_loopback=True)
    provider = OllamaProvider(ep)

    with pytest.raises(CorpusSieveError) as exc_info:
        provider.complete_structured(
            model_id="llama3:latest",
            schema=DummySchema,
            system="System",
            prompt="User",
            max_retries=1,
        )
    assert exc_info.value.code == ErrorCode.MODEL_SCHEMA_TEST_FAILED
