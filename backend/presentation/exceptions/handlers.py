"""
Global Exception Handlers for FastAPI Application.

This module centralizes all application-level exception handlers
to maintain clean separation from the main application file.
"""
from fastapi import FastAPI, Request
from backend.shared.utils.exception_handlers import handle_value_error, handle_import_error


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all global exception handlers with the FastAPI application.
    
    Centralizes exception handling registration to keep app.py clean
    and provide a single place to manage all application-level error handling.
    
    Args:
        app: FastAPI application instance to register handlers on
        
    Note:
        This function should be called during application initialization
        after the FastAPI app instance is created but before starting the server.
    """
    
    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """
        Handle configuration-related value errors.
        
        Specifically handles cases where LLM client configurations are invalid
        or unsupported LLM providers are selected, providing user-friendly
        error responses instead of generic 500 errors.
        
        Args:
            request: FastAPI request object for context
            exc: ValueError exception that was raised
            
        Returns:
            HTTPException: Formatted error response with appropriate status code
        
        Examples:
            - Invalid LLM provider configuration
            - Missing required configuration values
            - Unsupported LLM client types
        """
        return await handle_value_error(request, exc)
    
    @app.exception_handler(ImportError)
    async def import_error_handler(request: Request, exc: ImportError):
        """
        Handle import errors from missing dependencies or deleted modules.
        
        Provides graceful error handling when optional dependencies are missing
        or when modules have been removed, allowing the application to continue
        running with degraded functionality rather than crashing.
        
        Args:
            request: FastAPI request object for context
            exc: ImportError exception that was raised
            
        Returns:
            HTTPException: Formatted error response with appropriate status code
        
        Examples:
            - Optional LLM provider packages not installed
            - Deleted or moved modules still being referenced
            - Missing system dependencies
        """
        return await handle_import_error(request, exc)