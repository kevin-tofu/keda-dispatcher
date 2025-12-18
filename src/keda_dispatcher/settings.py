# app/settings.py
from __future__ import annotations
from dataclasses import dataclass
import os

from keda_dispatcher import __version__


def _env(name: str, default: str | None = None) -> str | None:
    return os.getenv(name, default)


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None:
        return default
    return int(v)


def _env_bool(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    """
    Runtime configuration loaded from environment variables.

    - APP_TITLE: default "ProcGate"
    - APP_VERSION: default package __version__
    - ENABLE_DOCS: default "false"
    - ROOT_PATH: default ""
    - HOST: default "0.0.0.0"
    - PORT: default 8080
    - WORKERS: default 1
    - LOG_LEVEL: default "info"
    - RELOAD: default "false"
    - REDIS_URL: default "redis://localhost:6379/0" (required)
    - QUEUE_KEY: default "queue:jobs"
    - R2_ENDPOINT_URL: optional, e.g. "https://<account>.r2.cloudflarestorage.com"
    - R2_ACCESS_KEY_ID: optional
    - R2_SECRET_ACCESS_KEY: optional
    - R2_BUCKET: default "proc-data"
    - EXTRA_API_MODULES: comma-separated "pkg.module:router_or_factory" list (optional)
    """
    # --- App ---
    app_title: str
    app_version: str
    enable_docs: bool
    root_path: str

    # --- Server run ---
    host: str
    port: int
    workers: int
    log_level: str
    reload: bool

    # --- Redis / Queue ---
    redis_url: str
    queue_key: str

    # --- Cloudflare R2 ---
    r2_endpoint_url: str | None
    r2_access_key_id: str | None
    r2_secret_access_key: str | None
    r2_bucket: str

    # --- Optional external routers (module path list "pkg.mod:router") ---
    extra_api_modules: tuple[str, ...] = ()

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            # App
            app_title=_env("APP_TITLE", "ProcGate") or "ProcGate",
            app_version=_env("APP_VERSION", __version__) or __version__,
            enable_docs=_env_bool("ENABLE_DOCS", False),
            root_path=_env("ROOT_PATH", "") or "",

            # Server
            host=_env("HOST", "0.0.0.0") or "0.0.0.0",
            port=_env_int("PORT", 8080),
            workers=_env_int("WORKERS", 1),
            log_level=_env("LOG_LEVEL", "info") or "info",
            reload=_env_bool("RELOAD", False),

            # Redis / Queue
            redis_url=_env("REDIS_URL", "redis://localhost:6379/0") or "redis://localhost:6379/0",
            queue_key=_env("QUEUE_KEY", "queue:jobs") or "queue:jobs",

            # R2
            r2_endpoint_url=_env("R2_ENDPOINT_URL"),
            r2_access_key_id=_env("R2_ACCESS_KEY_ID"),
            r2_secret_access_key=_env("R2_SECRET_ACCESS_KEY"),
            r2_bucket=_env("R2_BUCKET", "proc-data") or "proc-data",

            # External API routers
            extra_api_modules=tuple(
                [
                    x.strip()
                    for x in (_env("EXTRA_API_MODULES", "") or "").split(",")
                    if x.strip()
                ]
            ),
        )

    def validate(self) -> None:
        # 起動時に必須項目をチェックしたい場合
        # R2を必須にするならここで落とす、任意なら warn にするなど方針を決める
        if not self.redis_url:
            raise RuntimeError("REDIS_URL is required")

        # R2必須運用なら:
        # if not (self.r2_endpoint_url and self.r2_access_key_id and self.r2_secret_access_key):
        #     raise RuntimeError("R2 env is not configured")
