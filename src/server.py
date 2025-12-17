from __future__ import annotations
import argparse
import sys
from pathlib import Path
import uvicorn

# Ensure project root is importable when running as a script.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from settings import Settings
from app_factory import create_app  # create_app(cfg) を作ってる想定


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
    args = parser.parse_args()

    # CLIで上書きした Settings を生成（frozen なので新規生成）
    s = Settings(
        **{**s0.__dict__,
           "host": args.host,
           "port": args.port,
           "workers": args.workers,
           "log_level": args.log_level,
           "reload": args.reload,
           "enable_docs": (False if args.no_docs else s0.enable_docs)}
    )

    app = create_app(s)  # create_app が Settings を受け取る設計

    uvicorn.run(app, host=s.host, port=s.port, workers=s.workers, log_level=s.log_level, reload=s.reload)


if __name__ == "__main__":
    main()
