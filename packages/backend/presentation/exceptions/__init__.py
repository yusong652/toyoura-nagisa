"""
Presentation Layer Exception Handling.

This module provides centralized exception handling for the presentation layer
including HTTP error responses, WebSocket error handling, and API error formatting.

Exception Hierarchy (2025 Standard):
    ApiException (base)
    ├── BadRequestError (400)
    ├── InvalidInputError (422)
    ├── NotFoundError (404)
    │   ├── SessionNotFoundError
    │   ├── MessageNotFoundError
    │   ├── TaskNotFoundError
    │   └── FileNotFoundError
    ├── AccessDeniedError (403)
    ├── InternalServerError (500)
    ├── ServiceUnavailableError (503)
    └── ExternalServiceError (502)
"""

from .handlers import register_exception_handlers
from .api_exceptions import (
    ApiException,
    BadRequestError,
    InvalidInputError,
    NotFoundError,
    SessionNotFoundError,
    MessageNotFoundError,
    TaskNotFoundError,
    FileNotFoundError,
    AccessDeniedError,
    InternalServerError,
    ServiceUnavailableError,
    ExternalServiceError,
)

__all__ = [
    "register_exception_handlers",
    # API Exceptions
    "ApiException",
    "BadRequestError",
    "InvalidInputError",
    "NotFoundError",
    "SessionNotFoundError",
    "MessageNotFoundError",
    "TaskNotFoundError",
    "FileNotFoundError",
    "AccessDeniedError",
    "InternalServerError",
    "ServiceUnavailableError",
    "ExternalServiceError",
]