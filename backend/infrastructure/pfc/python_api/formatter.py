"""Documentation formatters for LLM consumption.

This module provides formatters that convert API documentation into
LLM-friendly markdown format. It handles:
- Brief signature formatting for quick reference
- Full documentation with examples and best practices
- Special formatting for Contact types
- Official API path generation
- Search result responses (no results, low confidence)
"""

from typing import Optional, Dict, Any, List
from backend.infrastructure.pfc.python_api.loader import DocumentationLoader
from backend.infrastructure.pfc.python_api.types.mappings import CLASS_TO_MODULE


class APIDocFormatter:
    """Formats API documentation as LLM-friendly markdown.

    This class provides static methods for formatting API documentation
    in various styles, optimized for LLM consumption and understanding.
    """

    @staticmethod
    def format_signature(api_name: str, metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Format brief one-liner signature for quick reference.

        Args:
            api_name: Full API name (e.g., "itasca.ball.create")
            metadata: Optional metadata from SearchResult (for Contact type info)

        Returns:
            Brief signature string with return type and description
            Format: "`signature` -> return_type - brief description"
            For Contact APIs: includes supported contact types
            Returns None if API not found

        Example:
            >>> APIDocFormatter.format_signature("Ball.vel")
            "`ball.vel() -> vec` - Get ball velocity vector"

            >>> APIDocFormatter.format_signature(
            ...     "itasca.BallBallContact.force_global",
            ...     {"all_contact_types": ["BallBallContact", "BallFacetContact", ...]}
            ... )
            "`contact.force_global() -> vec` - Get contact force (supports: BallBallContact, BallFacetContact, ...)"
        """
        api_doc = DocumentationLoader.load_api_doc(api_name)
        if not api_doc:
            return None

        # Extract first line of description (usually the summary)
        description_lines = api_doc['description'].strip().split('\n')
        brief_desc = description_lines[0].strip()

        # Get return type if available
        return_info = ""
        if api_doc.get('returns'):
            return_type = api_doc['returns']['type']
            return_info = f" -> {return_type}"

        # Add Contact type support information if available
        contact_suffix = ""
        if metadata and "all_contact_types" in metadata:
            contact_types = metadata["all_contact_types"]
            contact_suffix = f" (supports: {', '.join(contact_types)})"

        return f"`{api_doc['signature']}`{return_info} - {brief_desc}{contact_suffix}"

    @staticmethod
    def format_full_doc(
        api_doc: Dict[str, Any],
        api_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Format complete API documentation with Contact type support.

        Generates structured markdown with clear sections for LLM consumption:
        - Official API path (with Contact type mapping if applicable)
        - Signature and return type
        - Detailed description
        - Parameters with types and descriptions
        - Usage examples with code
        - Limitations and fallback commands
        - Best practices and notes

        Args:
            api_doc: Documentation dict from DocumentationLoader.load_api_doc()
            api_name: API name (e.g., "Ball.vel", "itasca.ball.create")
            metadata: Optional metadata dict (for Contact type info, etc.)

        Returns:
            Formatted markdown string

        Example output for Contact type:
            # itasca.BallBallContact.gap

            **Available for**: BallBallContact, BallFacetContact, ...

            **Signature**: `contact.gap() -> float`

            Get the gap between contact entities...

        Example output for regular API:
            # itasca.ball.create

            **Signature**: `ball.create(radius, pos=None)`

            Creates a new ball in the simulation...
        """
        lines = []

        # Generate official API path for display
        display_path = APIDocFormatter._get_display_path(api_name, metadata)

        # Header
        lines.append(f"# {display_path}")
        lines.append("")

        # Add Contact type availability info
        if metadata and 'all_contact_types' in metadata:
            all_types = metadata['all_contact_types']
            lines.append(f"**Available for**: {', '.join(all_types)}")
            lines.append("")

        # Signature
        lines.append(f"**Signature**: `{api_doc['signature']}`")
        lines.append("")

        # Description
        lines.append(api_doc['description'])
        lines.append("")

        # Parameters
        if api_doc.get('parameters'):
            lines.append("## Parameters")
            for param in api_doc['parameters']:
                required = "**required**" if param['required'] else "*optional*"
                lines.append(
                    f"- **`{param['name']}`** ({param['type']}, {required}): "
                    f"{param['description']}"
                )
            lines.append("")

        # Returns
        if api_doc.get('returns'):
            ret = api_doc['returns']
            lines.append("## Returns")
            lines.append(f"**`{ret['type']}`**: {ret['description']}")
            lines.append("")

        # Examples
        if api_doc.get('examples'):
            lines.append("## Examples")
            for i, ex in enumerate(api_doc['examples'], 1):
                lines.append(f"### Example {i}: {ex['description']}")
                lines.append("```python")
                lines.append(ex['code'])
                lines.append("```")
                lines.append("")

        # Limitations (IMPORTANT - guides LLM to command fallback)
        if api_doc.get('limitations'):
            lines.append("## Limitations")
            lines.append(api_doc['limitations'])
            lines.append("")

            if api_doc.get('fallback_commands'):
                lines.append(
                    f"**When to use commands instead**: "
                    f"{', '.join(api_doc['fallback_commands'])}"
                )
                lines.append("")

        # Best Practices
        if api_doc.get('best_practices'):
            lines.append("## Best Practices")
            for bp in api_doc['best_practices']:
                lines.append(f"- {bp}")
            lines.append("")

        # Notes
        if api_doc.get('notes'):
            lines.append("## Notes")
            for note in api_doc['notes']:
                lines.append(f"- {note}")
            lines.append("")

        # See Also
        if api_doc.get('see_also'):
            lines.append(f"**See Also**: {', '.join(api_doc['see_also'])}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _get_display_path(api_name: str, metadata: Optional[Dict[str, Any]]) -> str:
        """Generate official API path for display.

        Handles three cases:
        1. Contact types: itasca.{ContactType}.{method}
        2. Object methods: itasca.{module}.{Class}.{method}
        3. Module functions: itasca.{module}.{function}

        Args:
            api_name: Internal API name
            metadata: Optional metadata dict with contact_type info

        Returns:
            Official API path string

        Example:
            >>> _get_display_path("Contact.gap", {"contact_type": "BallBallContact"})
            "itasca.BallBallContact.gap"
            >>> _get_display_path("Ball.vel", None)
            "itasca.ball.Ball.vel"
            >>> _get_display_path("itasca.ball.create", None)
            "itasca.ball.create"
        """
        # Case 1: Contact types
        if metadata and 'contact_type' in metadata:
            contact_type = metadata['contact_type']
            method_name = api_name.split('.')[-1]  # Extract method from "Contact.gap"
            return f"itasca.{contact_type}.{method_name}"

        # Case 2: Object methods (e.g., "Ball.vel", "Wall.vel")
        if '.' in api_name and not api_name.startswith('itasca.'):
            class_name = api_name.split('.')[0]
            if class_name in CLASS_TO_MODULE:
                module_name = CLASS_TO_MODULE[class_name]
                return f"itasca.{module_name}.{api_name}"

        # Case 3: Module functions (already has full path)
        return api_name

    @staticmethod
    def format_no_results_response(query: str, hints: List[str] = None) -> str:
        """Format LLM content when no Python SDK API found.

        Args:
            query: Original search query
            hints: Optional list of hint messages from fallback_hints

        Returns:
            Formatted markdown string for LLM consumption

        Example output:
            **Python SDK**: Not available for this operation

            **Next Step**: Use pfc_query_command tool to search for PFC commands instead
        """
        hint_text = f"Note: {hints[0]}\n\n" if hints else ""

        return (
            f"**Python SDK**: Not available for this operation\n\n"
            f"{hint_text}"
            f"**Next Step**: Use pfc_query_command tool to search for PFC commands instead"
        )

