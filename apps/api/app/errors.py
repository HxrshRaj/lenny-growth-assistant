"""
Structured error handling. No endpoint should ever leak a raw stack trace to the
client -- every failure path returns {error, detail, code} with an appropriate
status code, and the real exception is logged server-side.
"""
import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

logger = logging.getLogger("lenny.errors")


class NotFoundError(Exception):
    def __init__(self, detail: str):
        self.detail = detail


class DatabaseUnavailableError(Exception):
    def __init__(self, detail: str = "The database is not reachable."):
        self.detail = detail


def _error_response(status_code: int, error: str, detail: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "detail": detail, "code": code},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def handle_not_found(request: Request, exc: NotFoundError):
        return _error_response(status.HTTP_404_NOT_FOUND, "not_found", exc.detail, "NOT_FOUND")

    @app.exception_handler(DatabaseUnavailableError)
    async def handle_db_unavailable(request: Request, exc: DatabaseUnavailableError):
        logger.error("database_unavailable", extra={"detail": exc.detail, "path": str(request.url)})
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "database_unavailable",
            exc.detail,
            "DB_UNAVAILABLE",
        )

    @app.exception_handler(OperationalError)
    async def handle_sqlalchemy_operational_error(request: Request, exc: OperationalError):
        logger.error("db_operational_error", extra={"path": str(request.url), "err": str(exc)})
        return _error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "database_unavailable",
            "The database is not reachable. Please try again shortly.",
            "DB_UNAVAILABLE",
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        return _error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_error",
            "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()),
            "VALIDATION_ERROR",
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException):
        return _error_response(exc.status_code, "http_error", str(exc.detail), "HTTP_ERROR")

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.exception("unhandled_exception", extra={"path": str(request.url)})
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred.",
            "INTERNAL_ERROR",
        )
