from __future__ import annotations
import argparse
import importlib
import uvicorn
from fastapi import APIRouter

from keda_dispatcher.settings import Settings
from keda_dispatcher.app_factory import create_app  # create_app(cfg) を作ってる想定


def load_external_routers(module_paths: tuple[str, ...]) -> list[APIRouter]:
    routers: list[APIRouter] = []
    for path in module_paths:
        mod_path, _, attr = path.partition(":")
        if not mod_path or not attr:
            raise RuntimeError(f"EXTRA_API_MODULES entry '{path}' is invalid. Use 'pkg.module:router_var_or_factory'.")

        mod = importlib.import_module(mod_path)
        obj = getattr(mod, attr)
        if isinstance(obj, APIRouter):
            router = obj
        elif callable(obj):
            router = obj()  # factory returning APIRouter
        else:
            raise RuntimeError(f"{path} must be an APIRouter or a factory returning APIRouter")
        routers.append(router)
    return routers


def main():
    s0 = Settings.from_env()
    s0.validate()

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default=s0.host)
    parser.add_argument("--port", "-P", type=int, default=s0.port)
    parser.add_argument("--workers", type=int, default=s0.workers)
    parser.add_argument("--log-level", type=str, default=s0.log_level)
    parser.add_argument("--reload", action="store_true", default=s0.reload)
    parser.add_argument("--no-docs", action="store_true")
    parser.add_argument(
        "--extra-router",
        action="append",
        default=list(s0.extra_api_modules),
        help="module.path:router_or_factory (repeatable)",
    )
    args = parser.parse_args()

    # CLIで上書きした Settings を生成（frozen なので新規生成）
    s = Settings(
        **{**s0.__dict__,
           "host": args.host,
           "port": args.port,
           "workers": args.workers,
           "log_level": args.log_level,
           "reload": args.reload,
           "enable_docs": (False if args.no_docs else s0.enable_docs),
           "extra_api_modules": tuple(args.extra_router or ()),
           }
    )

    external_routers = load_external_routers(s.extra_api_modules)

    app = create_app(s, extra_routers=external_routers)  # create_app が Settings を受け取る設計

    uvicorn.run(app, host=s.host, port=s.port, workers=s.workers, log_level=s.log_level, reload=s.reload)


if __name__ == "__main__":
    main()
