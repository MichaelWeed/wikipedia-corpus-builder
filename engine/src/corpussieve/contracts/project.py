from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from corpussieve.contracts.enums import JobState


class ProjectFile(BaseModel):
    """CorpusSieve project configuration file contract.

    CRITICAL INVARIANT (Design §21):
    No API keys, access tokens, or credentials may EVER be stored in project.yaml.
    Tokens must be stored strictly in system keyring via keyring references.
    """

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    project_id: str
    name: str
    created_at: str
    source_paths: list[str]
    source_adapter: str
    source_fingerprint: str | None = None
    domain_path: str
    lock_path: str
    output_dir: str
    provider_ref: str | None = None
    job_state: JobState = JobState.NEW

    @field_validator("provider_ref")
    @classmethod
    def validate_no_secrets(cls, v: str | None) -> str | None:
        if v is not None:
            v_lower = v.lower()
            if "bearer" in v_lower or "sk-" in v_lower or ("token" in v_lower and len(v) > 30):
                raise ValueError("Raw tokens or secrets are forbidden in project.yaml.")
        return v
