"""API path resolution for PFC SDK.

This module handles conversion between internal API paths and official
user-facing API paths.

Official path formats:
1. Contact types: itasca.{ContactType}.{method}
2. Object methods: itasca.{module}.{Class}.{method}
3. Module functions: itasca.{module}.{function}
"""

from typing import Optional
from backend.infrastructure.pfc.sdk.models import SearchResult
from backend.infrastructure.pfc.sdk.types.mappings import CLASS_TO_MODULE


class PathResolver:
    """Resolves internal API paths to official user-facing paths."""

    @staticmethod
    def resolve_display_path(result: SearchResult) -> str:
        """Convert internal API path to official user-facing path.

        Args:
            result: SearchResult with api_name and optional metadata

        Returns:
            Official API path string for user display

        Example:
            >>> # Contact type
            >>> result = SearchResult(
            ...     api_name="Contact.gap",
            ...     metadata={"contact_type": "BallBallContact"}
            ... )
            >>> PathResolver.resolve_display_path(result)
            "itasca.BallBallContact.gap"

            >>> # Object method
            >>> result = SearchResult(api_name="Ball.vel", metadata=None)
            >>> PathResolver.resolve_display_path(result)
            "itasca.ball.Ball.vel"

            >>> # Module function
            >>> result = SearchResult(
            ...     api_name="itasca.ball.create",
            ...     metadata=None
            ... )
            >>> PathResolver.resolve_display_path(result)
            "itasca.ball.create"
        """
        api_name = result.api_name
        metadata = result.metadata

        # Case 1: Contact types (special handling)
        # Internal: "Contact.gap"
        # Display: "itasca.BallBallContact.gap"
        if metadata and 'contact_type' in metadata:
            contact_type = metadata['contact_type']
            method_name = api_name.split('.')[-1]
            return f"itasca.{contact_type}.{method_name}"

        # Case 2: Object methods (e.g., "Ball.vel", "Wall.vel")
        # Internal: "Ball.vel"
        # Display: "itasca.ball.Ball.vel"
        if '.' in api_name and not api_name.startswith('itasca.'):
            class_name = api_name.split('.')[0]
            if class_name in CLASS_TO_MODULE:
                module_name = CLASS_TO_MODULE[class_name]
                return f"itasca.{module_name}.{api_name}"

        # Case 3: Module functions (already full path)
        # Internal: "itasca.ball.create"
        # Display: "itasca.ball.create"
        return api_name

    @staticmethod
    def get_internal_path(result: SearchResult) -> str:
        """Get the internal API path (for loading documentation).

        This is a convenience method that returns the api_name,
        which is always the internal path used for documentation lookup.

        Args:
            result: SearchResult object

        Returns:
            Internal API path string

        Example:
            >>> result = SearchResult(
            ...     api_name="Contact.gap",
            ...     metadata={"contact_type": "BallBallContact"}
            ... )
            >>> PathResolver.get_internal_path(result)
            "Contact.gap"
        """
        return result.api_name
