"""Regression tests for JWT verification (P0 auth-bypass fix).

Before the fix, ``decode_token`` decoded every token with
``verify_signature=False``, so anyone could forge ``{"sub": ..., "role":
"Owner"}``. These tests pin the verified behavior in all three modes:
prod-with-JWKS, prod-without-JWKS (fail-closed), and DEBUG/dev.
"""
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core import deps


@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _set(monkeypatch, **kwargs):
    """Override fields on the module-level settings used by decode_token."""
    for key, value in kwargs.items():
        monkeypatch.setattr(deps.settings, key, value, raising=False)


def _fake_jwks(monkeypatch, public_key):
    class _Key:
        key = public_key

    class _Client:
        def get_signing_key_from_jwt(self, token):
            return _Key()

    monkeypatch.setattr(deps, "_jwks_client", lambda url: _Client())


# ── Production WITH JWKS: signature is verified ──────────────────────────────

def test_valid_rs256_token_accepted(monkeypatch, rsa_keypair):
    private_key, public_key = rsa_keypair
    _set(monkeypatch, LOGTO_JWKS_URL="https://idp.example/jwks",
         LOGTO_AUDIENCE="", LOGTO_ISSUER="", DEBUG=False)
    _fake_jwks(monkeypatch, public_key)

    token = jwt.encode({"sub": "user-1", "role": "User"}, private_key, algorithm="RS256")
    claims = deps.decode_token(token)
    assert claims["sub"] == "user-1"


def test_token_signed_with_wrong_key_rejected(monkeypatch, rsa_keypair):
    _, public_key = rsa_keypair
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    _set(monkeypatch, LOGTO_JWKS_URL="https://idp.example/jwks",
         LOGTO_AUDIENCE="", LOGTO_ISSUER="", DEBUG=False)
    _fake_jwks(monkeypatch, public_key)  # JWKS serves the legitimate key

    forged = jwt.encode({"sub": "victim", "role": "Owner"}, attacker_key, algorithm="RS256")
    with pytest.raises(jwt.InvalidTokenError):
        deps.decode_token(forged)


def test_unsigned_alg_none_token_rejected(monkeypatch, rsa_keypair):
    _, public_key = rsa_keypair
    _set(monkeypatch, LOGTO_JWKS_URL="https://idp.example/jwks",
         LOGTO_AUDIENCE="", LOGTO_ISSUER="", DEBUG=False)
    _fake_jwks(monkeypatch, public_key)

    forged = jwt.encode({"sub": "victim", "role": "Owner"}, key="", algorithm="none")
    with pytest.raises(jwt.InvalidTokenError):
        deps.decode_token(forged)


def test_audience_enforced_when_configured(monkeypatch, rsa_keypair):
    private_key, public_key = rsa_keypair
    _set(monkeypatch, LOGTO_JWKS_URL="https://idp.example/jwks",
         LOGTO_AUDIENCE="dclaw-api", LOGTO_ISSUER="", DEBUG=False)
    _fake_jwks(monkeypatch, public_key)

    wrong_aud = jwt.encode(
        {"sub": "user-1", "aud": "some-other-api"}, private_key, algorithm="RS256"
    )
    with pytest.raises(jwt.InvalidTokenError):
        deps.decode_token(wrong_aud)


# ── Production WITHOUT JWKS: fail closed ─────────────────────────────────────

def test_prod_without_jwks_rejects_everything(monkeypatch):
    _set(monkeypatch, LOGTO_JWKS_URL="", DEBUG=False)
    forged = jwt.encode({"sub": "victim", "role": "Owner"}, "anything", algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        deps.decode_token(forged)


# ── DEBUG / dev: unsigned tokens allowed for local development ───────────────

def test_debug_mode_accepts_unsigned_token(monkeypatch):
    _set(monkeypatch, LOGTO_JWKS_URL="", LOGTO_AUDIENCE="", DEBUG=True)
    token = jwt.encode({"sub": "dev-user", "role": "Owner"}, "x", algorithm="HS256")
    claims = deps.decode_token(token)
    assert claims["sub"] == "dev-user"
