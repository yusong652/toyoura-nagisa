"""
Configuration validation utilities.
"""


async def validate_llm_configuration():
    """Validate LLM configuration at startup."""
    try:
        from backend.infrastructure.storage.llm_config_manager import get_default_llm_config
        config = get_default_llm_config()
        provider = config.get("provider") if config else "unknown"
        print(f"[OK] [STARTUP] LLM provider configured: {provider}")
    except Exception as e:
        print(f"[WARNING] [STARTUP] Could not validate LLM configuration: {e}")
