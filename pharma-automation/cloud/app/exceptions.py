"""Domain exceptions raised by service layer.

Services raise these instead of HTTPException to decouple business logic
from FastAPI. A global handler in main.py translates them to HTTP responses.
"""


class ServiceError(Exception):
    """Base for all domain exceptions."""

    status_code: int = 500

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


# --- 400 ---


class BadRequestError(ServiceError):
    status_code = 400


class InsufficientStockError(BadRequestError):
    pass


# --- 401 ---


class AuthenticationError(ServiceError):
    status_code = 401


class InvalidCredentialsError(AuthenticationError):
    pass


# --- 403 ---


class ForbiddenError(ServiceError):
    status_code = 403


# --- 404 ---


class NotFoundError(ServiceError):
    status_code = 404


class DrugNotFoundError(NotFoundError):
    pass


# --- 409 ---


class ConflictError(ServiceError):
    status_code = 409


class DuplicateEntryError(ConflictError):
    pass


class VersionConflictError(ConflictError):
    pass


# --- 422 ---


class ValidationError(ServiceError):
    status_code = 422
