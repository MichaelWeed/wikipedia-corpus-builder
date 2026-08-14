import contextlib
import os
from pathlib import Path
from typing import Any

import keyring
import platformdirs
import yaml  # type: ignore[import-untyped]

from corpussieve.contracts.providers import ProviderEndpoint

KEYRING_SERVICE = "corpussieve"


def get_config_dir() -> Path:
    """Return user configuration directory for CorpusSieve."""
    if "CORPUSSIEVE_CONFIG_DIR" in os.environ:
        d = Path(os.environ["CORPUSSIEVE_CONFIG_DIR"])
    else:
        d = Path(platformdirs.user_config_dir("corpussieve"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_providers_config_path() -> Path:
    """Return path to providers.yaml file."""
    return get_config_dir() / "providers.yaml"


def load_configured_endpoints() -> list[ProviderEndpoint]:
    """Load provider endpoints from providers.yaml config file."""
    p = get_providers_config_path()
    if not p.exists():
        return []

    try:
        content = p.read_text(encoding="utf-8")
        data = yaml.safe_load(content) or []
        if not isinstance(data, list):
            return []
        endpoints: list[ProviderEndpoint] = []
        for item in data:
            if isinstance(item, dict):
                endpoints.append(ProviderEndpoint.model_validate(item))
        return endpoints
    except Exception:
        return []


def save_configured_endpoints(endpoints: list[ProviderEndpoint]) -> None:
    """Save provider endpoints to providers.yaml (without tokens!)."""
    p = get_providers_config_path()
    clean_items: list[dict[str, Any]] = []

    for ep in endpoints:
        data = ep.model_dump(mode="json")
        clean_items.append(data)

    yaml_str = yaml.safe_dump(clean_items, sort_keys=False)
    p.write_text(yaml_str, encoding="utf-8")


def store_auth_token(token_ref: str, token_val: str) -> None:
    """Store provider authentication token securely in system keyring."""
    with contextlib.suppress(Exception):
        keyring.set_password(KEYRING_SERVICE, token_ref, token_val)


def get_auth_token(token_ref: str) -> str | None:
    """Retrieve provider authentication token from system keyring."""
    try:
        return keyring.get_password(KEYRING_SERVICE, token_ref)
    except Exception:
        return None
