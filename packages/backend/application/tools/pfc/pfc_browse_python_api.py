"""PFC Python API Browse Tool - Navigate and retrieve Python SDK documentation.

This tool provides hierarchical navigation through PFC Python SDK documentation,
using Python-native dot notation (e.g., itasca.ball.create, itasca.ball.Ball.pos).

Use pfc_query_python_api for keyword-based search when API path is unknown.
"""

from typing import Dict, Any, Optional, Tuple, List

from backend.application.tools.registrar import ToolRegistrar
from pydantic import Field

from backend.infrastructure.pfc.python_api import APILoader, APIFormatter
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response


def register_pfc_browse_python_api_tool(registrar: ToolRegistrar):
    """Register PFC Python API browse tool with the registrar."""

    @registrar.tool(
        tags={"pfc", "python", "api", "browse", "documentation"},
        annotations={"category": "pfc", "tags": ["pfc", "python", "api", "browse"]}
    )
    async def pfc_browse_python_api(
        api: Optional[str] = Field(
            None,
            description=(
                "PFC Python API path to browse (dot-separated, starting from itasca). Examples:\n"
                "- None or '': Root overview - all modules and objects\n"
                "- 'itasca': Core module functions (command, cycle, gravity, etc.)\n"
                "- 'itasca.ball': Ball module functions (create, find, list, etc.)\n"
                "- 'itasca.ball.create': Specific function documentation\n"
                "- 'itasca.ball.Ball': Ball object method groups\n"
                "- 'itasca.ball.Ball.pos': Specific method documentation\n"
                "- 'itasca.wall.facet': Nested submodule\n"
                "- 'itasca.wall.facet.Facet': Facet object in wall.facet module"
            )
        )
    ) -> Dict[str, Any]:
        """Browse PFC Python SDK documentation by path (like glob + cat).

        Paths use Python dot notation starting from 'itasca'.

        Navigation levels:
        - Root (no api): All modules and objects overview
        - Module (itasca.ball): Module functions list
        - Function (itasca.ball.create): Full function documentation
        - Object (itasca.ball.Ball): Object method groups
        - Method (itasca.ball.Ball.pos): Full method documentation

        When to use:
        - You know the API path (module.function or module.Object.method)
        - You want to explore available functions/methods

        Related tools:
        - pfc_query_python_api: Search API by keywords (when path unknown)
        - pfc_browse_commands: PFC command syntax documentation
        """
        try:
            # Normalize and parse API path
            normalized = _normalize_api_path(api)

            # Route to appropriate handler
            if not normalized:
                return _browse_root()

            if normalized == "itasca":
                return _browse_module("itasca")

            parsed = _parse_api_path(normalized)

            if parsed["type"] == "error":
                # Return parent level with error
                return _browse_with_fallback(parsed)

            if parsed["type"] == "module":
                return _browse_module(parsed["module_path"])
            elif parsed["type"] == "function":
                return _browse_function(parsed["module_path"], parsed["name"])
            elif parsed["type"] == "object":
                return _browse_object(
                    parsed["module_path"],
                    parsed["name"],
                    parsed.get("display_name")  # For Contact type aliases
                )
            elif parsed["type"] == "method":
                return _browse_method(
                    parsed["module_path"],
                    parsed["object_name"],
                    parsed["name"],
                    parsed.get("display_name")  # For Contact type aliases
                )
            else:
                return error_response(f"Unknown parse result type: {parsed['type']}")

        except FileNotFoundError as e:
            return error_response(f"Documentation not found: {str(e)}")
        except Exception as e:
            return error_response(f"Error browsing documentation: {str(e)}")



def _normalize_api_path(api: Optional[str]) -> str:
    """Normalize API path input."""
    if api is None:
        return ""
    # Strip whitespace and ensure lowercase for module parts
    return api.strip()


def _parse_api_path(api: str) -> Dict[str, Any]:
    """Parse API path and determine type.

    Returns dict with:
    - type: "module" | "function" | "object" | "method" | "error"
    - module_path: module path as string (e.g., "itasca.ball")
    - name: function/object/method name
    - object_name: for methods, the parent object name
    - error: error message if type is "error"
    - fallback_path: parent path for fallback on error
    """
    if not api.startswith("itasca"):
        return {
            "type": "error",
            "error": f"Path must start with 'itasca', got: {api}",
            "fallback_path": ""
        }

    parts = api.split(".")
    index = APILoader.load_index()
    modules = index.get("modules", {})
    objects = index.get("objects", {})

    # Find where the object starts (first capitalized part after itasca)
    object_index = None
    for i, part in enumerate(parts):
        if i > 0 and part[0].isupper():
            object_index = i
            break

    if object_index is not None:
        # Path contains an object
        module_parts = parts[:object_index]
        module_path = ".".join(module_parts)
        object_name = parts[object_index]

        # Check if object_name is a Contact type alias (BallBallContact, etc.)
        actual_object_name = object_name
        if object_name not in objects:
            # Check if it's a Contact type alias
            contact_data = objects.get("Contact", {})
            contact_types = contact_data.get("types", [])
            if object_name in contact_types:
                # It's a Contact type alias - use Contact as the actual object
                actual_object_name = "Contact"
            else:
                return {
                    "type": "error",
                    "error": f"Object '{object_name}' not found",
                    "fallback_path": module_path
                }

        if len(parts) == object_index + 1:
            # Just the object: itasca.ball.Ball or itasca.BallBallContact
            return {
                "type": "object",
                "module_path": module_path,
                "name": actual_object_name,
                "display_name": object_name  # Keep original name for display
            }
        else:
            # Object + method: itasca.ball.Ball.pos
            method_name = parts[object_index + 1]
            return {
                "type": "method",
                "module_path": module_path,
                "object_name": actual_object_name,
                "display_name": object_name,  # Keep original name for display
                "name": method_name
            }
    else:
        # No object in path - could be module or function
        # Try to find the longest matching module
        for length in range(len(parts), 0, -1):
            candidate = ".".join(parts[:length])
            # Check if this is a valid module path
            # Module keys in index: "itasca", "ball", "clump", "wall.facet", etc.
            # We need to map full path to index key
            index_key = _path_to_index_key(candidate)

            if index_key in modules:
                if length == len(parts):
                    # Exact module match
                    return {
                        "type": "module",
                        "module_path": candidate
                    }
                else:
                    # Module + function: itasca.ball.create
                    func_name = parts[length]
                    return {
                        "type": "function",
                        "module_path": candidate,
                        "name": func_name
                    }

        # No module match found
        return {
            "type": "error",
            "error": f"Module path not found: {api}",
            "fallback_path": ".".join(parts[:-1]) if len(parts) > 1 else ""
        }


def _path_to_index_key(full_path: str) -> str:
    """Convert full path to index key.

    Examples:
    - "itasca" -> "itasca"
    - "itasca.ball" -> "ball"
    - "itasca.wall.facet" -> "wall.facet"
    """
    if full_path == "itasca":
        return "itasca"
    if full_path.startswith("itasca."):
        return full_path[7:]  # Remove "itasca." prefix
    return full_path


def _index_key_to_path(index_key: str) -> str:
    """Convert index key to full path.

    Examples:
    - "itasca" -> "itasca"
    - "ball" -> "itasca.ball"
    - "wall.facet" -> "itasca.wall.facet"
    """
    if index_key == "itasca":
        return "itasca"
    return f"itasca.{index_key}"


def _browse_root() -> Dict[str, Any]:
    """Browse root level - overview of all modules and objects."""
    index = APILoader.load_index()
    modules = index.get("modules", {})
    objects = index.get("objects", {})

    content = APIFormatter.format_root(modules, objects)

    # Count objects for message (Contact types expand to multiple)
    object_count = 0
    for name, data in objects.items():
        if name == "Contact":
            contact_types = data.get("types", [])
            object_count += len(contact_types) if contact_types else 1
        else:
            object_count += 1

    return success_response(
        message=f"PFC Python SDK: {len(modules)} modules, {object_count} objects",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "root",
            "modules": list(modules.keys()),
            "objects": list(objects.keys())
        }
    )


def _browse_module(module_path: str) -> Dict[str, Any]:
    """Browse a specific module - list its functions."""
    index_key = _path_to_index_key(module_path)
    module_data = APILoader.load_module(index_key)

    if not module_data:
        return error_response(f"Module not found: {module_path}")

    functions = module_data.get("functions", [])

    # Find related objects in this module
    index = APILoader.load_index()
    objects = index.get("objects", {})
    related_objects = []
    for obj_name, obj_data in objects.items():
        file_path = obj_data.get("file", "")
        if index_key in file_path or (index_key == "itasca" and "/" not in file_path):
            related_objects.append(obj_name)

    content = APIFormatter.format_module(module_path, module_data, related_objects)

    return success_response(
        message=f"{module_path}: {len(functions)} functions",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "module",
            "module_path": module_path,
            "function_count": len(functions),
            "functions": [f.get("name") if isinstance(f, dict) else f for f in functions]
        }
    )


def _browse_function(module_path: str, func_name: str) -> Dict[str, Any]:
    """Browse a specific function documentation."""
    index_key = _path_to_index_key(module_path)
    func_doc = APILoader.load_function(index_key, func_name)

    if not func_doc:
        # Fallback to module level with error status
        error_msg = f"Function '{func_name}' not found in {module_path}"
        module_data = APILoader.load_module(index_key)
        if module_data:
            module_content = APIFormatter.format_module(module_path, module_data)
            fallback_content = APIFormatter.format_with_error(error_msg, module_content)
            return error_response(
                error_msg,
                llm_content={"parts": [{"type": "text", "text": fallback_content}]}
            )
        return error_response(error_msg)

    content = APIFormatter.format_function(func_doc, module_path)

    # Add navigation footer
    navigation = f"""

Navigation:
- pfc_browse_python_api(api="{module_path}") for module overview
- pfc_browse_python_api() for root
"""
    full_content = content + navigation

    return success_response(
        message=f"Documentation: {module_path}.{func_name}",
        llm_content={"parts": [{"type": "text", "text": full_content}]},
        data={
            "level": "function",
            "module_path": module_path,
            "function": func_name,
            "full_path": f"{module_path}.{func_name}"
        }
    )


def _browse_object(module_path: str, object_name: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    """Browse an object - list its method groups.

    Args:
        module_path: Module path (e.g., "itasca.ball" or "itasca")
        object_name: Actual object name in index (e.g., "Ball", "Contact")
        display_name: Display name for Contact types (e.g., "BallBallContact")
    """
    object_doc = APILoader.load_object(object_name)

    if not object_doc:
        return error_response(f"Object not found: {object_name}")

    shown_name = display_name or object_name
    method_groups = object_doc.get("method_groups", {})
    methods = object_doc.get("methods", [])
    full_path = f"{module_path}.{shown_name}"

    content = APIFormatter.format_object(module_path, object_name, object_doc, display_name)

    return success_response(
        message=f"{full_path}: {len(method_groups) or len(methods)} method groups/methods",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "object",
            "module_path": module_path,
            "object": shown_name,
            "full_path": full_path,
            "method_groups": list(method_groups.keys()) if method_groups else methods
        }
    )


def _browse_method(module_path: str, object_name: str, method_name: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    """Browse a specific method documentation.

    Args:
        module_path: Module path (e.g., "itasca.ball" or "itasca")
        object_name: Actual object name in index (e.g., "Ball", "Contact")
        method_name: Method name
        display_name: Display name for Contact types (e.g., "BallBallContact")
    """
    method_doc = APILoader.load_method(object_name, method_name)

    # Use display_name if provided (for Contact type aliases)
    shown_name = display_name or object_name

    if not method_doc:
        # Fallback to object level with error status
        error_msg = f"Method '{method_name}' not found in {shown_name}"
        object_doc = APILoader.load_object(object_name)
        if object_doc:
            object_content = APIFormatter.format_object(module_path, object_name, object_doc, display_name)
            fallback_content = APIFormatter.format_with_error(error_msg, object_content)
            return error_response(
                error_msg,
                llm_content={"parts": [{"type": "text", "text": fallback_content}]}
            )
        return error_response(error_msg)

    # Pass both shown_name (for display) and object_name (for component detection)
    content = APIFormatter.format_method(method_doc, shown_name, actual_object_name=object_name)

    full_path = f"{module_path}.{shown_name}"
    navigation = f"""

Navigation:
- pfc_browse_python_api(api="{full_path}") for object overview
- pfc_browse_python_api(api="{module_path}") for module overview
"""
    full_content = content + navigation

    return success_response(
        message=f"Documentation: {shown_name}.{method_name}",
        llm_content={"parts": [{"type": "text", "text": full_content}]},
        data={
            "level": "method",
            "module_path": module_path,
            "object": shown_name,
            "method": method_name,
            "full_path": f"{full_path}.{method_name}"
        }
    )


def _browse_with_fallback(parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Handle error case by falling back to parent level with error status."""
    error_msg = parsed.get("error", "Unknown error")
    fallback_path = parsed.get("fallback_path", "")

    # Determine fallback content using formatter
    if not fallback_path:
        # Fall back to root
        index = APILoader.load_index()
        modules = index.get("modules", {})
        objects = index.get("objects", {})
        fallback_content_raw = APIFormatter.format_root(modules, objects)
    else:
        # Try to browse fallback path
        normalized = _normalize_api_path(fallback_path)
        if not normalized or normalized == "itasca":
            index = APILoader.load_index()
            modules = index.get("modules", {})
            objects = index.get("objects", {})
            fallback_content_raw = APIFormatter.format_root(modules, objects)
        else:
            # Re-parse and get content
            re_parsed = _parse_api_path(normalized)
            if re_parsed["type"] == "module":
                index_key = _path_to_index_key(re_parsed["module_path"])
                module_data = APILoader.load_module(index_key)
                if module_data:
                    fallback_content_raw = APIFormatter.format_module(re_parsed["module_path"], module_data)
                else:
                    # Module not found, fall back to root
                    index = APILoader.load_index()
                    modules = index.get("modules", {})
                    objects = index.get("objects", {})
                    fallback_content_raw = APIFormatter.format_root(modules, objects)
            elif re_parsed["type"] == "object":
                object_doc = APILoader.load_object(re_parsed["name"])
                if object_doc:
                    fallback_content_raw = APIFormatter.format_object(
                        re_parsed["module_path"], re_parsed["name"], object_doc
                    )
                else:
                    # Object not found, fall back to root
                    index = APILoader.load_index()
                    modules = index.get("modules", {})
                    objects = index.get("objects", {})
                    fallback_content_raw = APIFormatter.format_root(modules, objects)
            else:
                index = APILoader.load_index()
                modules = index.get("modules", {})
                objects = index.get("objects", {})
                fallback_content_raw = APIFormatter.format_root(modules, objects)

    # Format with error and return error response
    fallback_content = APIFormatter.format_with_error(error_msg, fallback_content_raw)
    return error_response(
        error_msg,
        llm_content={"parts": [{"type": "text", "text": fallback_content}]}
    )
