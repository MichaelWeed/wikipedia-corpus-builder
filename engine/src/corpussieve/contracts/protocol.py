from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from corpussieve.contracts.errors import ErrorCode


class JsonRpcRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str | None = None
    method: str
    params: dict[str, Any] = {}


class JsonRpcErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    message: str
    detail: dict[str, Any] = {}


class JsonRpcError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: int
    message: str
    data: JsonRpcErrorDetail | None = None


class JsonRpcResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"] = "2.0"
    id: int | str | None = None
    result: Any | None = None
    error: JsonRpcError | None = None


class JsonRpcNotification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    jsonrpc: Literal["2.0"] = "2.0"
    method: str
    params: dict[str, Any] = {}
