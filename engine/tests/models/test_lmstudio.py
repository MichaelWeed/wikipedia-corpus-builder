import json
from typing import Literal

import pytest
import respx
from pydantic import BaseModel

from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.providers import ProviderEndpoint
from corpussieve.models.lmstudio import LMSTUDIO_DEFAULT_URL, LMStudioProvider


class DummySchema(BaseModel):
    decision: Literal["include", "exclude"]
    reason: str


def test_lmstudio_detect_success(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(f"{LMSTUDIO_DEFAULT_URL}/v1/models").respond(
        status_code=200, json={"data": [{"id": "meta-llama-3"}]}
    )

    ep = LMStudioProvider.detect()
    assert ep is not None
    assert ep.provider == "lmstudio"
    assert ep.base_url == LMSTUDIO_DEFAULT_URL


def test_lmstudio_list_models(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(f"{LMSTUDIO_DEFAULT_URL}/v1/models").respond(
        status_code=200,
        json={
            "data": [
                {"id": "meta-llama-3", "type": "chat"},
                {"id": "text-embedding-nomic", "type": "embedding"},
            ]
        },
    )

    ep = ProviderEndpoint(provider="lmstudio", base_url=LMSTUDIO_DEFAULT_URL, is_loopback=True)
    provider = LMStudioProvider(ep)

    models = provider.list_models()
    assert len(models) == 1
    assert models[0].model_id == "meta-llama-3"


def test_lmstudio_complete_structured_happy_path(
    respx_mock: respx.MockRouter,
) -> None:
    respx_mock.post(f"{LMSTUDIO_DEFAULT_URL}/v1/chat/completions").respond(
        status_code=200,
        json={
            "choices": [
                {"message": {"content": json.dumps({"decision": "include", "reason": "Relevant"})}}
            ]
        },
    )

    ep = ProviderEndpoint(provider="lmstudio", base_url=LMSTUDIO_DEFAULT_URL, is_loopback=True)
    provider = LMStudioProvider(ep)

    res = provider.complete_structured(
        model_id="meta-llama-3",
        schema=DummySchema,
        system="System prompt",
        prompt="User prompt",
    )
    assert isinstance(res, DummySchema)
    assert res.decision == "include"


def test_lmstudio_auth_failed(respx_mock: respx.MockRouter) -> None:
    respx_mock.get(f"{LMSTUDIO_DEFAULT_URL}/v1/models").respond(status_code=401)

    ep = ProviderEndpoint(provider="lmstudio", base_url=LMSTUDIO_DEFAULT_URL, is_loopback=True)
    provider = LMStudioProvider(ep)

    with pytest.raises(CorpusSieveError) as exc_info:
        provider.list_models()
    assert exc_info.value.code == ErrorCode.MODEL_AUTH_FAILED
