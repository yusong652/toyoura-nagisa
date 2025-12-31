# FastAPI Standards Guide (2025)

This guide defines the API design standards for the toyoura-nagisa project, ensuring consistent, type-safe, and maintainable endpoints.

## Table of Contents

1. [Response Format](#response-format)
2. [Exception Handling](#exception-handling)
3. [Route Design](#route-design)
4. [Request/Response Models](#requestresponse-models)
5. [Dependency Injection](#dependency-injection)
6. [Migration Guide](#migration-guide)

---

## Response Format

All API endpoints return `ApiResponse[T]` for type-safe responses:

```python
from backend.presentation.models.api_models import ApiResponse

class SessionData(BaseModel):
    id: str
    name: str

@router.get("/sessions/{id}", response_model=ApiResponse[SessionData])
async def get_session(id: str) -> ApiResponse[SessionData]:
    return ApiResponse(
        success=True,
        message="Session retrieved",
        data=SessionData(id=id, name="My Session")
    )
```

### ApiResponse Structure

| Field | Type | Description |
|-------|------|-------------|
| `success` | `bool` | Whether the operation succeeded |
| `message` | `str` | Human-readable status message |
| `data` | `Optional[T]` | Response payload (null on error) |
| `error_code` | `Optional[str]` | Error code for client handling |

### Example Responses

**Success:**
```json
{
  "success": true,
  "message": "Session created successfully",
  "data": {
    "session_id": "abc-123"
  },
  "error_code": null
}
```

**Error:**
```json
{
  "detail": {
    "error_code": "SESSION_NOT_FOUND",
    "message": "Session 'abc-123' not found",
    "details": {
      "session_id": "abc-123"
    }
  }
}
```

---

## Exception Handling

Use standardized exception classes from `backend.presentation.exceptions`:

```python
from backend.presentation.exceptions import (
    SessionNotFoundError,
    InvalidInputError,
    InternalServerError,
)

@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    result = await service.get(session_id)
    if not result:
        raise SessionNotFoundError(session_id)  # 404
    return ApiResponse(success=True, message="OK", data=result)
```

### Exception Hierarchy

```
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
```

### Custom Exception Example

```python
class WorkspaceNotFoundError(NotFoundError):
    def __init__(self, workspace_id: str):
        super().__init__(
            resource_type="WORKSPACE",
            resource_id=workspace_id,
            message=f"Workspace '{workspace_id}' not found"
        )
```

---

## Route Design

Follow RESTful conventions:

### HTTP Methods

| Method | Usage | Example |
|--------|-------|---------|
| `GET` | Retrieve resource(s) | `GET /sessions` |
| `POST` | Create resource | `POST /sessions` |
| `PUT` | Replace resource | `PUT /sessions/{id}` |
| `PATCH` | Partial update | `PATCH /sessions/{id}` |
| `DELETE` | Remove resource | `DELETE /sessions/{id}` |

### URL Patterns

```python
# Collection
@router.get("/sessions")                    # List all
@router.post("/sessions")                   # Create new

# Single resource
@router.get("/sessions/{id}")               # Get one
@router.put("/sessions/{id}")               # Replace
@router.patch("/sessions/{id}")             # Update
@router.delete("/sessions/{id}")            # Delete

# Sub-resources
@router.get("/sessions/{id}/messages")      # List messages
@router.get("/sessions/{id}/token-usage")   # Get usage

# Actions (use POST for non-CRUD operations)
@router.post("/sessions/switch")            # Switch session
@router.post("/sessions/{id}/archive")      # Archive session
```

### Deprecation

When changing routes, keep old ones with `deprecated=True`:

```python
@router.post("/history", response_model=ApiResponse[SessionCreateData])
async def create_session(...):
    """New endpoint."""
    ...

@router.post("/history/create", deprecated=True)
async def create_session_legacy(...):
    """[DEPRECATED] Use POST /history instead."""
    return await create_session(...)
```

---

## Request/Response Models

Define models close to their endpoints for clarity:

```python
# =====================
# Response Data Models
# =====================
class SessionData(BaseModel):
    """Session metadata for API responses."""
    id: str = Field(..., description="Session UUID")
    name: str = Field(..., description="Session display name")
    created_at: str = Field(..., description="Creation timestamp")

# =====================
# Request Models
# =====================
class CreateSessionRequest(BaseModel):
    """Request body for creating a new session."""
    name: Optional[str] = Field(None, description="Session name")
```

### Field Definitions

Use explicit `default=` for optional fields (Pylance compatibility):

```python
# Required field
name: str = Field(..., description="Required field")

# Optional field with None default
notes: Optional[str] = Field(default=None, description="Optional field")

# Optional field with value default
count: int = Field(default=0, description="Defaults to 0")
```

### Field Validation

Use Pydantic validators for business rules:

```python
from pydantic import field_validator

class ExecuteRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=10000)
    timeout_ms: Optional[int] = Field(default=None, ge=100, le=300000)

    @field_validator('command')
    @classmethod
    def validate_command(cls, v: str) -> str:
        if v.strip().startswith('rm -rf /'):
            raise ValueError("Dangerous command detected")
        return v
```

---

## Dependency Injection

Use `Depends()` for services and resources:

```python
from fastapi import Depends, Request

def get_session_service() -> SessionService:
    """Dependency injection for SessionService."""
    return SessionService()

def get_llm_client(request: Request) -> LLMClientBase:
    """Get LLM client from app state."""
    return request.app.state.llm_client

@router.get("/sessions/{id}")
async def get_session(
    id: str,
    service: SessionService = Depends(get_session_service),
    llm_client: LLMClientBase = Depends(get_llm_client)
):
    ...
```

---

## Migration Guide

### Before (Legacy Pattern)

```python
@router.post("/history/create", response_model=dict)
async def create_session(request: NewHistoryRequest) -> dict:
    try:
        result = await service.create_session(...)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### After (2025 Standard)

```python
@router.post("/history", response_model=ApiResponse[SessionCreateData])
async def create_session(
    request: CreateSessionRequest,
    service: SessionService = Depends(get_session_service)
) -> ApiResponse[SessionCreateData]:
    try:
        result = await service.create_session(...)
        return ApiResponse(
            success=True,
            message="Session created",
            data=SessionCreateData(session_id=result["session_id"])
        )
    except Exception as e:
        raise InternalServerError(message=str(e))
```

### Checklist

- [ ] Replace `response_model=dict` with `ApiResponse[T]`
- [ ] Define specific data models for responses
- [ ] Use standardized exceptions instead of `HTTPException`
- [ ] Update route paths to RESTful pattern
- [ ] Add deprecated routes for backward compatibility
- [ ] Use `Depends()` for service injection
- [ ] Add `Field()` descriptions to all model fields

---

## Reference Files

| File | Purpose |
|------|---------|
| `presentation/models/api_models.py` | ApiResponse, StandardErrorResponse |
| `presentation/exceptions/api_exceptions.py` | Exception classes |
| `presentation/api/sessions.py` | Reference implementation |

---

**Last Updated:** 2025-12-31
