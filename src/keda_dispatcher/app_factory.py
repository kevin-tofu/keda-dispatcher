# app/app_factory.py
from __future__ import annotations

from dataclasses import dataclass
from fastapi import FastAPI

from keda_dispatcher.api.proc import router as proc_router


@dataclass(frozen=True)
class AppConfig:
    title: str = "ProcGate"
    version: str = "0.1.0"
    enable_docs: bool = True
    root_path: str = ""  # 例: /api (Ingressのprefix運用時)


def create_app(cfg: AppConfig | None = None) -> FastAPI:
    cfg = cfg or AppConfig()
    # Settings と AppConfig の両方に対応するため属性名を柔軟に読む
    title = getattr(cfg, "title", getattr(cfg, "app_title", "ProcGate"))
    version = getattr(cfg, "version", getattr(cfg, "app_version", "0.1.0"))
    enable_docs = getattr(cfg, "enable_docs", True)
    root_path = getattr(cfg, "root_path", "")

    # docsを切りたい運用もあるので条件化
    docs_url = "/docs" if enable_docs else None
    redoc_url = "/redoc" if enable_docs else None
    openapi_url = "/openapi.json" if enable_docs else None

    app = FastAPI(
        title=title,
        version=version,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        root_path=root_path,
    )

    app.include_router(proc_router)
    return app
