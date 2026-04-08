"""Rate limiting configuration using slowapi."""
import jwt as _jwt
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


limiter = Limiter(key_func=get_remote_address)


def get_pharmacy_key(request: Request) -> str:
    """Extract pharmacy_id from JWT for pharmacy-scoped rate limiting."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            from app.config import settings

            payload = _jwt.decode(
                auth[7:],
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            return f"pharmacy:{payload.get('pharmacy_id', 'unknown')}"
        except Exception:
            pass
    return get_remote_address(request)
