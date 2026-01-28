"""
Global Exception Handlers Module

Provides standardized exception handling logic, particularly for LLM configuration and import errors.
"""

from fastapi import Request
from fastapi.responses import JSONResponse


async def handle_value_error(request: Request, exc: ValueError) -> JSONResponse:
    """
    Handle configuration-related value errors, particularly when an LLM client is unsupported.
    """
    error_message = str(exc)
    
    # Check if it's an LLM client related error
    if "Unsupported LLM client" in error_message or "Unknown LLM client" in error_message:
        return JSONResponse(
            status_code=400,
            content={
                "error": "LLM Configuration Error",
                "message": error_message,
                "type": "unsupported_llm_client",
                "suggestion": "Please update your configuration to use 'gemini' as the LLM client."
            }
        )
    
    # Other value errors
    return JSONResponse(
        status_code=400,
        content={
            "error": "Configuration Error",
            "message": error_message,
            "type": "value_error"
        }
    )


async def handle_import_error(request: Request, exc: ImportError) -> JSONResponse:
    """
    Handle import errors, typically caused by missing dependencies or deleted modules.
    """
    error_message = str(exc)
    
    # Check if it's an LLM client related import error
    if any(client in error_message for client in ["gpt", "anthropic", "mistral", "grok"]):
        return JSONResponse(
            status_code=500,
            content={
                "error": "LLM Client Import Error",
                "message": "Legacy LLM clients have been removed in the new architecture.",
                "type": "deprecated_client",
                "details": error_message,
                "solution": "Please configure your system to use 'gemini' as the LLM client."
            }
        )
    
    # Other import errors
    return JSONResponse(
        status_code=500,
        content={
            "error": "Import Error",
            "message": error_message,
            "type": "import_error"
        }
    )
