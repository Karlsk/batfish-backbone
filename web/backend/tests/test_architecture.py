from pathlib import Path

import pytest

from tests.architecture_rules import check_sources


@pytest.mark.parametrize(
    "path,source",
    [
        ("app/modules/a/api.py", "import pybatfish.client.session"),
        ("app/modules/a/service.py", "from pybatfish.client.session import Session as S"),
        ("app/modules/a/service.py", "from app.infrastructure.sdk import factory"),
        ("app/modules/a/service.py", "from app.modules.b.repository import Repository"),
        ("app/modules/a/service.py", "from ..b import controller as adapter"),
        ("app/modules/a/service.py", "from app.modules import b"),
        ("app/modules/a/api.py", "from .controller import run"),
        ("app/modules/a/api.py", "from . import repository"),
        ("app/modules/a/controller.py", "from .service import Service"),
        ("app/modules/a/repository.py", "from .controller import query"),
        ("app/modules/a/service.py", "from fastapi import Request"),
        ("app/modules/a/archive.py", "from .service import Service"),
        ("app/modules/a/api.py", "from .archive import prepare"),
        ("app/modules/a/archive.py", "from app.modules.b.repository import Repository"),
        ("app/modules/a/service.py", "from app.composition import create_app"),
        ("app/modules/a/api.py", "from app.modules.b.service import Service"),
        ("app/contracts/models.py", "from app.modules.a.service import Service"),
        ("app/infrastructure/settings.py", "from app.modules.a.repository import Repository"),
        (
            "app/modules/a/service.py",
            "import importlib\nsdk = importlib.import_module('pybatfish')",
        ),
        ("app/modules/a/service.py", "sdk = __import__('pybatfish')"),
    ],
)
def test_import_boundaries_reject_violations(path, source):
    assert check_sources({path: source}), (path, source)


@pytest.mark.parametrize(
    "path,source",
    [
        ("app/modules/a/api.py", "from .service import Service"),
        ("app/modules/a/repository.py", "from .archive import prepare"),
        ("app/modules/a/archive.py", "from .schemas import UploadInput"),
        ("app/modules/a/service.py", "from app.modules.b.service import Service"),
        ("app/modules/a/service.py", "from ..b import service as b_service"),
        ("app/modules/a/service.py", "from . import controller, repository"),
        ("app/modules/a/controllers/routing.py", "from pybatfish.client.session import Session"),
        (
            "app/modules/a/controller.py",
            "from app.infrastructure.sdk.factory import SessionFactory",
        ),
        ("app/infrastructure/sdk/factory.py", "from pybatfish.client.session import Session"),
        (
            "app/composition.py",
            "from app.modules.a.api import router\nfrom app.modules.a.service import Service",
        ),
        ("app/modules/a/schemas.py", "from app.contracts.dto import Actor"),
        ("app/modules/a/service.py", "# import pybatfish\ntext = 'from .api import router'"),
    ],
)
def test_import_boundaries_allow_expected_dependencies(path, source):
    assert not check_sources({path: source})


def test_cross_module_service_cycles_are_rejected():
    sources = {
        "app/modules/a/service.py": "from app.modules.b.service import Service",
        "app/modules/b/service.py": "from app.modules.a.service import Service",
    }
    assert any("cycle" in violation for violation in check_sources(sources))


def test_import_boundaries_in_application():
    root = Path(__file__).resolve().parents[1]
    sources = {p.relative_to(root).as_posix(): p.read_text() for p in (root / "app").rglob("*.py")}
    assert sources, "No application source was checked"
    assert check_sources(sources) == []
