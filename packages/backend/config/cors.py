"""CORS (Cross-Origin Resource Sharing) configuration."""

import os
from typing import List
from pydantic import BaseModel, Field


class CORSConfig(BaseModel):
    """CORS configuration settings."""

    # Allowed origins (domains that can access the API)
    allow_origins: List[str] = Field(
        default_factory=list,
        description="List of allowed origins for CORS"
    )

    # Allow credentials (cookies, authorization headers)
    allow_credentials: bool = Field(
        default=True,
        description="Allow cookies and authorization headers"
    )

    # Allowed HTTP methods
    allow_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        description="Allowed HTTP methods"
    )

    # Allowed headers
    allow_headers: List[str] = Field(
        default=[
            "Content-Type",
            "Authorization",
            "Accept",
            "Origin",
            "X-Requested-With",
            "X-Session-ID",
        ],
        description="Allowed request headers"
    )

    # Preflight request cache duration (seconds)
    max_age: int = Field(
        default=600,
        description="How long browsers can cache preflight responses (seconds)"
    )


class DevelopmentCORSConfig(CORSConfig):
    """CORS configuration for development environment."""

    allow_origins: List[str] = Field(
        default=[
            "http://localhost:5173",      # Web frontend (Vite default)
            "http://localhost:3000",      # Alternative web port
            "http://127.0.0.1:5173",      # Localhost alias
            "http://127.0.0.1:3000",      # Localhost alias
            "http://localhost:8000",      # Backend self-reference
            "http://127.0.0.1:8000",      # Backend self-reference
        ]
    )

    # In development, we might want to allow additional headers for debugging
    allow_headers: List[str] = Field(
        default=[
            "Content-Type",
            "Authorization",
            "Accept",
            "Origin",
            "X-Requested-With",
            "X-Session-ID",
            "X-Debug-Token",              # Development debugging
            "X-Request-ID",               # Request tracing
        ]
    )


class StagingCORSConfig(CORSConfig):
    """CORS configuration for staging environment."""

    allow_origins: List[str] = Field(
        default=[
            # ⚠️ CUSTOMIZE THESE FOR YOUR STAGING ENVIRONMENT
            "https://staging.yourdomain.com",
            "https://staging-web.yourdomain.com",
        ]
    )


class ProductionCORSConfig(CORSConfig):
    """CORS configuration for production environment."""

    allow_origins: List[str] = Field(
        default=[
            # ⚠️ CUSTOMIZE THESE FOR YOUR PRODUCTION ENVIRONMENT
            # Never use "*" in production!
            "https://yourdomain.com",
            "https://www.yourdomain.com",
        ]
    )

    # Production should have stricter settings
    max_age: int = Field(
        default=3600,  # Cache for 1 hour in production
        description="Preflight cache duration"
    )


def get_cors_config() -> CORSConfig:
    """
    Get CORS configuration based on current environment.

    Returns:
        CORSConfig: Environment-specific CORS configuration

    Environment Variables:
        ENVIRONMENT: Set to 'development', 'staging', or 'production'
        CORS_ALLOWED_ORIGINS: Comma-separated list of additional allowed origins

    Examples:
        # Development (default)
        ENVIRONMENT=development

        # Production with custom domains
        ENVIRONMENT=production
        CORS_ALLOWED_ORIGINS=https://app.example.com,https://admin.example.com

        # Staging
        ENVIRONMENT=staging
        CORS_ALLOWED_ORIGINS=https://staging.example.com
    """
    environment = os.getenv("ENVIRONMENT", "development").lower()

    # Select config based on environment
    if environment == "production":
        config = ProductionCORSConfig()
    elif environment == "staging":
        config = StagingCORSConfig()
    else:
        config = DevelopmentCORSConfig()

    # Allow runtime override via environment variable
    additional_origins = os.getenv("CORS_ALLOWED_ORIGINS", "")
    if additional_origins:
        origins = [origin.strip() for origin in additional_origins.split(",")]
        config.allow_origins.extend(origins)
        print(f"[CORS] Added additional origins from environment: {origins}")

    # Log CORS configuration (helpful for debugging)
    print(f"[CORS] Environment: {environment}")
    print(f"[CORS] Allowed origins: {config.allow_origins}")
    print(f"[CORS] Allow credentials: {config.allow_credentials}")
    print(f"[CORS] Allowed methods: {config.allow_methods}")

    return config


# Convenience function for FastAPI middleware
def get_cors_middleware_kwargs() -> dict:
    """
    Get CORS middleware configuration as dict for FastAPI.

    Returns:
        dict: Configuration dict for CORSMiddleware

    Example:
        from backend.config.cors import get_cors_middleware_kwargs
        from fastapi.middleware.cors import CORSMiddleware

        app.add_middleware(CORSMiddleware, **get_cors_middleware_kwargs())
    """
    config = get_cors_config()
    return {
        "allow_origins": config.allow_origins,
        "allow_credentials": config.allow_credentials,
        "allow_methods": config.allow_methods,
        "allow_headers": config.allow_headers,
        "max_age": config.max_age,
    }
