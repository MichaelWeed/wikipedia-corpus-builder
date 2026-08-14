from corpussieve.contracts.errors import CorpusSieveError, ErrorCode
from corpussieve.contracts.providers import ProviderEndpoint
from corpussieve.models.base import ModelProvider


def detect_all() -> list[ProviderEndpoint]:
    """Detect available local model providers (Ollama then LM Studio)."""
    detected: list[ProviderEndpoint] = []

    # Defer imports to avoid circular dependencies
    from corpussieve.models.lmstudio import LMStudioProvider
    from corpussieve.models.ollama import OllamaProvider

    ollama_ep = OllamaProvider.detect()
    if ollama_ep:
        detected.append(ollama_ep)

    lmstudio_ep = LMStudioProvider.detect()
    if lmstudio_ep:
        detected.append(lmstudio_ep)

    return detected


def provider_for(endpoint: ProviderEndpoint) -> ModelProvider:
    """Return instantiated ModelProvider for given ProviderEndpoint."""
    from corpussieve.models.lmstudio import LMStudioProvider
    from corpussieve.models.ollama import OllamaProvider

    if endpoint.provider == "ollama":
        return OllamaProvider(endpoint)
    elif endpoint.provider == "lmstudio":
        return LMStudioProvider(endpoint)
    else:
        raise CorpusSieveError(
            ErrorCode.MODEL_UNREACHABLE,
            f"Unsupported provider type '{endpoint.provider}'",
        )
