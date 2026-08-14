from pydantic import BaseModel, ConfigDict


class ProgressEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    stage: str
    completed_units: int
    total_units: int | None = None
    message: str
