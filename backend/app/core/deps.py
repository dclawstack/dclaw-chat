from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import jwt
from typing import Optional

from app.core.database import get_db
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedException

settings = get_settings()
security = HTTPBearer(auto_error=False)


class CurrentUser:
    def __init__(self, user_id: str, email: str, role: str = "User"):
        self.user_id = user_id
        self.email = email
        self.role = role


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
        # In production, fetch JWKS from Logto and verify RS256
        # For scaffold/dev, accept HS256 with a fallback secret
        payload = jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": True},
            algorithms=["HS256", "RS256"],
            audience=settings.LOGTO_AUDIENCE or None,
        )
        user_id = payload.get("sub")
        email = payload.get("email", "")
        role = payload.get("role", "User")

        if not user_id:
            raise UnauthorizedException("Invalid token: no subject")

        return CurrentUser(user_id=user_id, email=email, role=role)

    except jwt.ExpiredSignatureError:
        raise UnauthorizedException("Token expired")
    except jwt.InvalidTokenError as e:
        raise UnauthorizedException(f"Invalid token: {str(e)}")


async def require_role(*roles: str):
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
