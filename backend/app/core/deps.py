from fastapi import Depends, HTTPException, WebSocket, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError
from functools import lru_cache
from typing import Optional

from app.core.database import get_db
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedException

settings = get_settings()
security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    """One cached JWKS client per URL (it caches signing keys internally)."""
    return PyJWKClient(jwks_url)


def decode_token(token: str) -> dict:
    """Decode and **verify** a JWT, returning its claims.

    Production (JWKS configured via ``AUTH_JWKS_URL``, falling back to the
    legacy ``LOGTO_JWKS_URL``): the RS256 signature is verified against the
    IdP's JWKS (works for Clerk, Logto, or any RS256 issuer), together with
    ``exp`` and — when configured — ``aud``/``iss``. Any failure raises
    ``jwt.InvalidTokenError``.

    Dev/scaffold (``DEBUG`` true and no JWKS configured): signature verification
    is skipped so local development works without a real IdP. This path is never
    reached in production because ``DEBUG`` defaults to ``False`` and, absent a
    JWKS URL, unverified tokens are rejected outright.
    """
    jwks_url = settings.auth_jwks_url
    audience = settings.auth_audience
    issuer = settings.auth_issuer

    if jwks_url:
        try:
            signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
        except PyJWKClientError as e:
            raise jwt.InvalidTokenError(f"Unable to resolve signing key: {e}") from e
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience or None,
            issuer=issuer or None,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": bool(audience),
                "verify_iss": bool(issuer),
            },
        )

    if settings.DEBUG:
        return jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": True},
            algorithms=["HS256", "RS256"],
            audience=audience or None,
        )

    raise jwt.InvalidTokenError(
        "JWT signature cannot be verified: AUTH_JWKS_URL (or legacy LOGTO_JWKS_URL) "
        "is not configured"
    )


class CurrentUser:
    def __init__(self, user_id: str, email: str, role: str = "User",
                 organizations=None):
        self.user_id = user_id
        self.email = email
        self.role = role
        # Logto organization ids from the token (enterprise SSO, #35).
        # None/[] for tokens without organization context.
        self.organizations = organizations or []


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> CurrentUser:
    if not credentials:
        if settings.DEBUG:
            return CurrentUser(user_id="dev-user", email="dev@localhost", role="Owner")
        raise UnauthorizedException("Missing authorization header")

    token = credentials.credentials
    if not token:
        raise UnauthorizedException("Missing token")

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        email = payload.get("email", "")
        role = payload.get("role", "User")

        if not user_id:
            raise UnauthorizedException("Invalid token: no subject")

        # Logto organization context (#35): either an `organizations` claim or
        # organization-token audiences (urn:logto:organization:<id>).
        orgs = list(payload.get("organizations") or [])
        aud = payload.get("aud")
        for a in aud if isinstance(aud, list) else ([aud] if aud else []):
            if isinstance(a, str) and a.startswith("urn:logto:organization:"):
                orgs.append(a.removeprefix("urn:logto:organization:"))

        return CurrentUser(user_id=user_id, email=email, role=role, organizations=orgs)

    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Token expired")
    except jwt.InvalidTokenError as e:
        raise UnauthorizedException(f"Invalid token: {str(e)}")


def authenticate_websocket(websocket: WebSocket) -> Optional[tuple[str, str]]:
    """Derive ``(user_id, user_name)`` from a verified token on a WebSocket.

    The token is read from the ``token`` query param or the ``access_token``
    cookie and verified via :func:`decode_token` (RS256/JWKS in production).
    Identity is taken only from the verified claims — never from client-supplied
    ``user_id``/``user_name`` query params. Returns ``None`` when authentication
    fails (caller should close with code 1008).
    """
    token = websocket.query_params.get("token") or websocket.cookies.get("access_token")

    if not token:
        if settings.DEBUG:
            return ("dev-user", "You")
        return None

    try:
        payload = decode_token(token)
    except jwt.InvalidTokenError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None
    user_name = payload.get("name") or payload.get("email") or "User"
    return (user_id, user_name)


def require_role(*roles: str):
    """Sync factory returning a dependency that gates a route on the caller's role.

    Owner is always allowed. Must be a plain ``def`` so ``Depends(require_role(...))``
    receives the inner ``checker`` coroutine function — an ``async def`` factory
    would instead hand FastAPI an un-awaited coroutine and silently never gate.
    """
    async def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in roles and user.role != "Owner":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {', '.join(roles)}",
            )
        return user
    return checker


async def get_db_session() -> AsyncSession:
    async for session in get_db():
        return session
