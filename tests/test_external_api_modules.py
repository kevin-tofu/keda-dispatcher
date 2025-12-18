import sys
import types
from pathlib import Path

from fastapi import APIRouter

# Ensure src is importable when running tests
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from keda_dispatcher.server import load_external_routers  # noqa: E402


def test_load_external_routers_from_var_and_factory():
    mod_name = "external_dummy"
    module = types.ModuleType(mod_name)
    module.router = APIRouter(prefix="/var")

    def _factory():
        return APIRouter(prefix="/factory")

    module.get_router = _factory
    sys.modules[mod_name] = module

    try:
        routers = load_external_routers((f"{mod_name}:router", f"{mod_name}:get_router"))
    finally:
        sys.modules.pop(mod_name, None)

    assert len(routers) == 2
    assert isinstance(routers[0], APIRouter)
    assert isinstance(routers[1], APIRouter)
    assert routers[0].prefix == "/var"
    assert routers[1].prefix == "/factory"
