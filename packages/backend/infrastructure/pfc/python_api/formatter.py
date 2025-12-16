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
    def _detect_component_methods(object_name: str, method_name: str) -> List[str]:
        """Detect if a method has component alternatives (_x, _y, _z).

        Checks the object's method_groups or methods list to see if component
        methods exist for the given base method.

        Args:
            object_name: Object class name (e.g., "Ball", "Wall")
            method_name: Base method name (e.g., "vel", "pos")

        Returns:
            List of component suffixes (['x', 'y', 'z']) if components exist,
            empty list otherwise.

        Example:
            >>> APIDocFormatter._detect_component_methods("Ball", "vel")
            ['x', 'y', 'z']  # If vel_x, vel_y, vel_z exist
            >>> APIDocFormatter._detect_component_methods("Ball", "id")
            []  # No component methods for id()
        """
        try:
            object_doc = DocumentationLoader.load_object(object_name)
            if not object_doc:
                return []

            # Collect all method names from both method_groups and methods list
            all_method_names = set()

            # Strategy 1: Check method_groups (Ball, Clump, etc.)
            method_groups = object_doc.get("method_groups", {})
            for group_methods in method_groups.values():
                if isinstance(group_methods, list):
                    all_method_names.update(group_methods)

            # Strategy 2: Check flat methods list (Wall, Contact, etc.)
            methods = object_doc.get("methods", [])
            for method in methods:
                if isinstance(method, dict):
                    all_method_names.add(method.get("name", ""))
                elif isinstance(method, str):
                    all_method_names.add(method)

            # Check if base method and component methods exist
            has_base = method_name in all_method_names
            has_x = f"{method_name}_x" in all_method_names
            has_y = f"{method_name}_y" in all_method_names
            has_z = f"{method_name}_z" in all_method_names

            # If base method exists and at least one component exists, return components
            if has_base:
                components = []
                if has_x:
                    components.append('x')
                if has_y:
                    components.append('y')
                if has_z:
                    components.append('z')

                return components

            return []

        except Exception:
            # If any error occurs during detection, fail silently
            return []

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

        # Add component access information if available
        component_suffix = ""
        if metadata and "has_components" in metadata:
            components = metadata["has_components"]
            component_suffix = f" [has _{', _'.join(components)} components]"

        return f"`{api_doc['signature']}`{return_info} - {brief_desc}{contact_suffix}{component_suffix}"

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

        # Add component access info if available
        if metadata and 'has_components' in metadata:
            components = metadata['has_components']
            method_name = api_name.split('.')[-1]
            component_list = ', '.join([f"`{method_name}_{c}()`" for c in components])
            lines.append(f"**Component Access**: {component_list}")
            lines.append("")
            lines.append(f"This method returns a vector. Individual components can be accessed via:")
            for c in components:
                lines.append(f"- `{method_name}_{c}()` - Get {c}-component only")
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

    @staticmethod
    def format_function(func_doc: Dict[str, Any], module_path: str) -> str:
        """Format function documentation for browse tool.

        Args:
            func_doc: Function documentation dict
            module_path: Full module path (e.g., "itasca.ball")

        Returns:
            LLM-friendly formatted markdown
        """
        lines = []

        name = func_doc.get("name", "")
        signature = func_doc.get("signature", f"{module_path}.{name}()")
        description = func_doc.get("description", "")

        lines.append(f"## {module_path}.{name}")
        lines.append("")
        lines.append(f"Signature: `{signature}`")
        lines.append("")
        lines.append(description)
        lines.append("")

        # Parameters
        params = func_doc.get("parameters", [])
        if params:
            lines.append("Parameters:")
            for param in params:
                pname = param.get("name", "")
                ptype = param.get("type", "")
                required = param.get("required", False)
                pdesc = param.get("description", "")
                req_str = "required" if required else "optional"
                lines.append(f"- {pname} ({ptype}, {req_str}): {pdesc}")
            lines.append("")

        # Returns
        returns = func_doc.get("returns", {})
        if returns:
            rtype = returns.get("type", "")
            rdesc = returns.get("description", "")
            lines.append(f"Returns: {rtype} - {rdesc}")
            lines.append("")

        # Limitations
        limitations = func_doc.get("limitations")
        if limitations:
            lines.append(f"Limitations: {limitations}")
            lines.append("")

        # Examples
        examples = func_doc.get("examples", [])
        if examples:
            lines.append("Example:")
            lines.append("```python")
            lines.append(examples[0].get("code", ""))
            lines.append("```")

        return "\n".join(lines)

    @staticmethod
    def format_method(method_doc: Dict[str, Any], object_name: str, actual_object_name: str = None) -> str:
        """Format method documentation for browse tool.

        Args:
            method_doc: Method documentation dict
            object_name: Display object name (e.g., "Ball", "BallBallContact")
            actual_object_name: Actual object name for loading documentation
                               (e.g., "Contact" when object_name is "BallBallContact")

        Returns:
            LLM-friendly formatted markdown
        """
        lines = []

        name = method_doc.get("name", "")
        signature = method_doc.get("signature", f"{object_name.lower()}.{name}()")
        description = method_doc.get("description", "")

        lines.append(f"## {object_name}.{name}")
        lines.append("")
        lines.append(f"Signature: `{signature}`")
        lines.append("")
        lines.append(description)
        lines.append("")

        # Parameters
        params = method_doc.get("parameters", [])
        if params:
            lines.append("Parameters:")
            for param in params:
                pname = param.get("name", "")
                ptype = param.get("type", "")
                required = param.get("required", False)
                pdesc = param.get("description", "")
                req_str = "required" if required else "optional"
                lines.append(f"- {pname} ({ptype}, {req_str}): {pdesc}")
            lines.append("")

        # Returns (with enhanced vec type information)
        returns = method_doc.get("returns", {})
        if returns:
            rtype = returns.get("type", "")
            rdesc = returns.get("description", "")

            # Enhance vec type description with indexing info
            if rtype == "vec":
                rdesc_enhanced = f"{rdesc} (indexable: [0]=x, [1]=y, [2]=z)"
                lines.append(f"Returns: {rtype} - {rdesc_enhanced}")
            else:
                lines.append(f"Returns: {rtype} - {rdesc}")
            lines.append("")

        # Component method detection and hints
        # Detect if this method has component alternatives (_x, _y, _z)
        # Use actual_object_name if provided (for Contact type aliases)
        lookup_name = actual_object_name or object_name
        components = APIDocFormatter._detect_component_methods(lookup_name, name)
        if components:
            component_list = ', '.join([f"`{name}_{c}()`" for c in components])
            lines.append(f"Component Access: {component_list}")
            lines.append("")
            lines.append("This method returns a vector. Individual components can be accessed via:")
            for c in components:
                lines.append(f"- `{name}_{c}()` - Get {c}-component only")
            lines.append("")

        # Examples
        examples = method_doc.get("examples", [])
        if examples:
            lines.append("Example:")
            lines.append("```python")
            lines.append(examples[0].get("code", ""))
            lines.append("```")

        return "\n".join(lines)

