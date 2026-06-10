"""Regression tests for P3 prod-hardening guards (T3-07, T3-08)."""
import importlib
import sys
from contextlib import contextmanager

import pytest

from app.core.config import Settings


# --- T3-07: prod must refuse to boot with the DEBUG Owner backdoor ---------

def test_assert_safe_blocks_production_with_debug():
    settings = Settings(ENVIRONMENT="production", DEBUG=True)
    with pytest.raises(RuntimeError, match="DEBUG"):
        settings.assert_safe_for_environment()


@pytest.mark.parametrize("env", ["production", "prod", "PRODUCTION", " Prod "])
def test_is_production_recognizes_prod_markers(env):
    assert Settings(ENVIRONMENT=env).is_production is True


def test_assert_safe_allows_production_without_debug():
    Settings(ENVIRONMENT="production", DEBUG=False).assert_safe_for_environment()


def test_assert_safe_allows_dev_with_debug():
    # DEBUG is fine outside production.
    Settings(ENVIRONMENT="development", DEBUG=True).assert_safe_for_environment()


# --- T3-08: docs/openapi are exposed only in DEBUG -------------------------

@contextmanager
def reloaded_app(monkeypatch, *, environment, debug):
    """Reimport app.main under the given env, then fully restore the original
    module object so conftest's dependency_overrides survive for later tests."""
    from app.core import config as config_module

    original_main = sys.modules.get("app.main")
    with monkeypatch.context() as mp:
        mp.setenv("ENVIRONMENT", environment)
        mp.setenv("DEBUG", str(debug).lower())
        config_module.get_settings.cache_clear()
        sys.modules.pop("app.main", None)
        try:
            yield importlib.import_module("app.main")
        finally:
            config_module.get_settings.cache_clear()
            if original_main is not None:
                sys.modules["app.main"] = original_main
            else:
                sys.modules.pop("app.main", None)


def test_docs_disabled_in_production(monkeypatch):
    with reloaded_app(monkeypatch, environment="production", debug=False) as main:
        assert main.app.docs_url is None
        assert main.app.redoc_url is None
        assert main.app.openapi_url is None


def test_docs_enabled_in_debug(monkeypatch):
    with reloaded_app(monkeypatch, environment="development", debug=True) as main:
        assert main.app.docs_url == "/docs"
        assert main.app.openapi_url == "/openapi.json"
