"""
Gemini API Constants Definition

This module contains constant definitions used in Gemini API processing,
primarily for filtering Pydantic model metadata attributes to avoid deprecation warnings.
"""

# Collection of Pydantic model metadata attributes
# These attributes are marked as deprecated in Pydantic V2.11+ and need to be filtered out to avoid warnings
PYDANTIC_METADATA_ATTRS = {
    'model_fields',           # Model field definitions
    'model_computed_fields',  # Computed field definitions
    'model_config',          # Model configuration
    'model_extra',           # Extra fields settings
    'model_fields_set',      # Set of fields that have been set
    'model_validator',       # Model validators
    'model_construct',       # Model construction method
    'model_copy',           # Model copy method
    'model_dump',           # Model export method
    'model_dump_json',      # JSON export method
    'model_json_schema',    # JSON schema generation
    'model_rebuild',        # Model rebuild method
    'model_validate',       # Model validation method
    'model_validate_json',  # JSON validation method
    'model_validate_strings' # String validation method
}
