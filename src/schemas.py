from __future__ import annotations
from typing import Any, Optional, Dict
from pydantic.dataclasses import dataclass


@dataclass
class ProcDataResponse:
    process_id: str


@dataclass
class RunRequest:
    job_type: str = "default"
    params: Dict[str, Any] | None = None  # どうしても任意パラメータ必要ならここに寄せる

@dataclass
class RunResponse:
    enqueued: bool
    process_id: str
    queue_key: str


@dataclass
class ProcStatusResponse:
    process_id: str
    status: str
    created_at: str
    updated_at: str
    content_type: str = ""
    original_filename: str = ""
    r2_bucket: str = ""
    r2_key: str = ""
    error: str = ""

@dataclass
class JobMessage:
    process_id: str
    job_type: str
    params: Dict[str, Any]
    enqueued_at: str
    r2_bucket: str
    r2_key: str


@dataclass
class ProcCreateResponse:
    process_id: str
