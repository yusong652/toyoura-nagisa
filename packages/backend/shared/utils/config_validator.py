"""
Configuration validation utilities.
"""


async def validate_llm_configuration():
    """Validate LLM configuration at startup."""
    try:
        from backend.config.llm import get_llm_settings
        provider = get_llm_settings().provider
        print(f"[OK] [STARTUP] LLM provider configured: {provider}")
    except Exception as e:
        print(f"[WARNING] [STARTUP] Could not validate LLM configuration: {e}")
