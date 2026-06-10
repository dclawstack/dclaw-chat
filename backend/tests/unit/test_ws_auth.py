"""Tests for the shared WebSocket authenticator (consensus #2).

calls/huddles/messaging WS endpoints all derive identity from a verified token
via ``authenticate_websocket`` — never from a client-supplied ``user_id``.
"""
import jwt
import pytest

from app.core import deps
from app.core.deps import authenticate_websocket


class _FakeWS:
    def __init__(self, query=None, cookies=None):
        self.query_params = query or {}
        self.cookies = cookies or {}


def test_no_token_rejected_when_not_debug(monkeypatch):
    monkeypatch.setattr(deps.settings, "DEBUG", False, raising=False)
    # Even a client-supplied user_id must be ignored — no token => None.
    assert authenticate_websocket(_FakeWS(query={"user_id": "victim"})) is None


def test_no_token_dev_fallback_when_debug(monkeypatch):
    monkeypatch.setattr(deps.settings, "DEBUG", True, raising=False)
    assert authenticate_websocket(_FakeWS()) == ("dev-user", "You")


def test_invalid_token_rejected(monkeypatch):
    monkeypatch.setattr(deps.settings, "DEBUG", False, raising=False)
    monkeypatch.setattr(deps, "decode_token", lambda t: (_ for _ in ()).throw(jwt.InvalidTokenError("bad")))
    assert authenticate_websocket(_FakeWS(query={"token": "forged"})) is None


def test_valid_token_yields_verified_identity(monkeypatch):
    monkeypatch.setattr(deps.settings, "DEBUG", False, raising=False)
    monkeypatch.setattr(deps, "decode_token", lambda t: {"sub": "user-7", "name": "Real Name"})
    # client tries to spoof a different user_id in the query — must be ignored.
    result = authenticate_websocket(_FakeWS(query={"token": "ok", "user_id": "victim"}))
    assert result == ("user-7", "Real Name")


def test_token_from_cookie(monkeypatch):
    monkeypatch.setattr(deps.settings, "DEBUG", False, raising=False)
    monkeypatch.setattr(deps, "decode_token", lambda t: {"sub": "user-9", "email": "u@x.io"})
    result = authenticate_websocket(_FakeWS(cookies={"access_token": "ok"}))
    assert result == ("user-9", "u@x.io")
