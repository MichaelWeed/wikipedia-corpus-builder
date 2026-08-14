import httpx

from corpussieve.contracts.errors import CorpusSieveError, ErrorCode


def classify_httpx_error(exc: Exception, provider_name: str, base_url: str) -> CorpusSieveError:
    """Classify httpx exceptions into CorpusSieveError failure classes."""
    if isinstance(exc, CorpusSieveError):
        return exc

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (401, 403):
            return CorpusSieveError(
                ErrorCode.MODEL_AUTH_FAILED,
                f"Authentication failed for {provider_name} at '{base_url}' (HTTP {status}).",
                detail={"provider": provider_name, "base_url": base_url, "status": status},
            )
        if status == 404:
            return CorpusSieveError(
                ErrorCode.MODEL_UNREACHABLE,
                f"Endpoint route mismatch for {provider_name} at '{base_url}' (HTTP 404).",
                detail={
                    "provider": provider_name,
                    "base_url": base_url,
                    "status": 404,
                    "kind": "endpoint_mismatch",
                },
            )
        return CorpusSieveError(
            ErrorCode.MODEL_UNREACHABLE,
            f"HTTP error for {provider_name} at '{base_url}': status {status}",
            detail={"provider": provider_name, "base_url": base_url, "status": status},
        )

    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError)):
        return CorpusSieveError(
            ErrorCode.MODEL_UNREACHABLE,
            f"Failed to connect to {provider_name} at '{base_url}': {exc}",
            detail={"provider": provider_name, "base_url": base_url, "error": str(exc)},
        )

    return CorpusSieveError(
        ErrorCode.MODEL_UNREACHABLE,
        f"Unexpected error communicating with {provider_name} at '{base_url}': {exc}",
        detail={"provider": provider_name, "base_url": base_url, "error": str(exc)},
    )
