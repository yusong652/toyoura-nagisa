"""
Standardized API Exception Classes (2025 Standard).

Provides a hierarchy of API exceptions for consistent error handling across all endpoints.
All exceptions inherit from ApiException and automatically format responses using
StandardErrorResponse for uniform client-side error handling.

Usage:
    from backend.presentation.exceptions import SessionNotFoundError, InvalidInputError

    @router.get("/sessions/{session_id}")
    async def get_session(session_id: str):
        session = await service.get(session_id)
        if not session:
            raise SessionNotFoundError(session_id)
        return ApiResponse(success=True, message="OK", data=session)
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException

from backend.presentation.models.api_models import StandardErrorResponse


class ApiException(HTTPException):
    """Base API exception with standardized error response format.

    All API exceptions should inherit from this class to ensure consistent
    error response structure across the application.
    """

    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        self.error_code = error_code
        self.error_message = message
        self.details = details

        detail = StandardErrorResponse(
            error_code=error_code,
            message=message,
            details=details
        ).model_dump()

        super().__init__(status_code=status_code, detail=detail)


# =====================
# 4xx Client Errors
# =====================
class BadRequestError(ApiException):
    """400 Bad Request - Invalid request syntax or parameters."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=400,
            error_code="BAD_REQUEST",
            message=message,
            details=details
        )


class InvalidInputError(ApiException):
    """422 Unprocessable Entity - Validation failed for request data."""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            status_code=422,
            error_code="INVALID_INPUT",
            message=message,
            details={"field": field} if field else None
        )


class NotFoundError(ApiException):
    """404 Not Found - Base class for resource not found errors."""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        message: Optional[str] = None
    ):
        super().__init__(
            status_code=404,
            error_code=f"{resource_type.upper()}_NOT_FOUND",
            message=message or f"{resource_type} '{resource_id}' not found",
            details={f"{resource_type.lower()}_id": resource_id}
        )


class SessionNotFoundError(NotFoundError):
    """404 Not Found - Session does not exist."""

    def __init__(self, session_id: str):
        super().__init__(
            resource_type="SESSION",
            resource_id=session_id,
            message=f"Session '{session_id}' not found"
        )


class MessageNotFoundError(NotFoundError):
    """404 Not Found - Message does not exist."""

    def __init__(self, message_id: str, session_id: Optional[str] = None):
        details_msg = f"Message '{message_id}' not found"
        if session_id:
            details_msg += f" in session '{session_id}'"
        super().__init__(
            resource_type="MESSAGE",
            resource_id=message_id,
            message=details_msg
        )


class TaskNotFoundError(NotFoundError):
    """404 Not Found - Task does not exist."""

    def __init__(self, task_id: str):
        super().__init__(
            resource_type="TASK",
            resource_id=task_id,
            message=f"Task '{task_id}' not found"
        )


class FileNotFoundError(NotFoundError):
    """404 Not Found - File does not exist."""

    def __init__(self, file_path: str):
        super().__init__(
            resource_type="FILE",
            resource_id=file_path,
            message=f"File '{file_path}' not found"
        )


class AccessDeniedError(ApiException):
    """403 Forbidden - Access to resource is denied."""

    def __init__(self, resource: str, reason: Optional[str] = None):
        message = f"Access denied to '{resource}'"
        if reason:
            message += f": {reason}"
        super().__init__(
            status_code=403,
            error_code="ACCESS_DENIED",
            message=message,
            details={"resource": resource, "reason": reason}
        )


# =====================
# 5xx Server Errors
# =====================
class InternalServerError(ApiException):
    """500 Internal Server Error - Unexpected server-side error."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=500,
            error_code="INTERNAL_ERROR",
            message=message,
            details=details
        )


class ServiceUnavailableError(ApiException):
    """503 Service Unavailable - External service is unavailable."""

    def __init__(self, service_name: str, message: Optional[str] = None):
        super().__init__(
            status_code=503,
            error_code="SERVICE_UNAVAILABLE",
            message=message or f"{service_name} is currently unavailable",
            details={"service": service_name}
        )


class ExternalServiceError(ApiException):
    """502 Bad Gateway - Error from external service."""

    def __init__(self, service_name: str, message: str):
        super().__init__(
            status_code=502,
            error_code="EXTERNAL_SERVICE_ERROR",
            message=f"{service_name} error: {message}",
            details={"service": service_name}
        )
