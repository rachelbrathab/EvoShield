"""Application exception taxonomy and FastAPI exception handlers.

Every business error derives from `AppError`. Routes raise typed errors and
let the framework translate them into consistent JSON responses — the error
contract the frontend can rely on:

    {"error": {"code": "not_found", "message": "…"}}
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for all application-level errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "internal_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class ProviderError(AppError):
    """Failure of an external provider (Supabase, GitHub OAuth, scanners…)."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "provider_error"


class ValidationFailedError(AppError):
    """Request validation failed outside FastAPI's default handler."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "validation_failed"


def register_exception_handlers(app: FastAPI) -> None:
    """Attach JSON exception handlers to the application."""

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning("AppError %s on %s %s", exc.code, request.method, request.url.path)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {"code": "internal_error", "message": "An unexpected error occurred."}
            },
        )
