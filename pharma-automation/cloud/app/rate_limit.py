"""Rate limiting configuration using slowapi."""
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

limiter = Limiter(key_func=get_remote_address)


def get_pharmacy_key(request: Request) -> str:
    """Extract pharmacy_id from JWT for pharmacy-scoped rate limiting.

    Uses the shared decode_jwt_payload helper from dependencies.py
    to avoid duplicating JWT decoding logic.
    """
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            from app.dependencies import decode_jwt_payload

            payload = decode_jwt_payload(auth[7:])
            return f"pharmacy:{payload.get('pharmacy_id', 'unknown')}"
        except Exception:
            pass
    return get_remote_address(request)
