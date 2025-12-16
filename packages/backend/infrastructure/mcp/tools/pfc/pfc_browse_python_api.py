"""PFC Python API Browse Tool - Navigate and retrieve Python SDK documentation.

This tool provides hierarchical navigation through PFC Python SDK documentation,
using Python-native dot notation (e.g., itasca.ball.create, itasca.ball.Ball.pos).

Use pfc_query_python_api for keyword-based search when API path is unknown.
"""

from typing import Dict, Any, Optional, Tuple, List
from fastmcp import FastMCP
from pydantic import Field

from backend.infrastructure.pfc.python_api import APILoader, APIFormatter
from backend.infrastructure.mcp.utils.tool_result import success_response, error_response


def register_pfc_browse_python_api_tool(mcp: FastMCP):
    """Register PFC Python API browse tool with the MCP server."""

    @mcp.tool(
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

    print("[DEBUG] Registered PFC Python API browse tool: pfc_browse_python_api")


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

    # Build modules list
    module_lines = []
    for key, data in modules.items():
        full_path = _index_key_to_path(key)
        func_count = len(data.get("functions", []))
        desc = data.get("description", "")
        if len(desc) > 50:
            desc = desc[:47] + "..."
        module_lines.append(f"- {full_path} ({func_count} funcs): {desc}")

    # Build objects list
    object_lines = []
    for name, data in objects.items():
        method_count = len(data.get("methods", data.get("method_groups", {}).keys()))
        desc = data.get("description", "")
        if len(desc) > 50:
            desc = desc[:47] + "..."
        # Find which module contains this object
        file_path = data.get("file", "")
        if "ball" in file_path:
            obj_path = f"itasca.ball.{name}"
        elif "clump/pebble" in file_path:
            obj_path = f"itasca.clump.pebble.{name}"
        elif "clump/template" in file_path:
            obj_path = f"itasca.clump.template.{name}"
        elif "clump" in file_path:
            obj_path = f"itasca.clump.{name}"
        elif "wall/facet" in file_path:
            obj_path = f"itasca.wall.facet.{name}"
        elif "wall/vertex" in file_path:
            obj_path = f"itasca.wall.vertex.{name}"
        elif "wall" in file_path:
            obj_path = f"itasca.wall.{name}"
        elif "measure" in file_path:
            obj_path = f"itasca.measure.{name}"
        else:
            obj_path = name

        # Handle Contact types - they are in itasca root namespace
        if name == "Contact":
            # Contact is a base interface, actual types are BallBallContact, etc.
            contact_types = data.get("types", [])
            if contact_types:
                # Add each contact type as itasca.XxxContact
                for ct in contact_types:
                    object_lines.append(f"- itasca.{ct}: {desc}")
                continue  # Skip the generic Contact entry
            else:
                obj_path = f"itasca.{name}"

        object_lines.append(f"- {obj_path}: {desc}")

    content = f"""## PFC Python SDK Documentation

Modules ({len(modules)}):
{chr(10).join(module_lines)}

Objects ({len(object_lines)}):
{chr(10).join(object_lines)}

Navigation:
- pfc_browse_python_api(api="itasca.ball") for module functions
- pfc_browse_python_api(api="itasca.ball.Ball") for object methods
- pfc_browse_python_api(api="itasca.ball.create") for function doc
- pfc_browse_python_api(api="itasca.ball.Ball.pos") for method doc

Search: pfc_query_python_api(query="...") for keyword search
"""

    return success_response(
        message=f"PFC Python SDK: {len(modules)} modules, {len(object_lines)} objects",
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
    description = module_data.get("description", "")

    # Build function list
    func_lines = []
    for func in functions:
        if isinstance(func, dict):
            name = func.get("name", "")
            sig = func.get("signature", "")
            desc = func.get("description", "")
            if len(desc) > 60:
                desc = desc[:57] + "..."
            func_lines.append(f"- {name}: {desc}")
        else:
            # Just function name from index
            func_lines.append(f"- {func}")

    # Find related objects in this module
    index = APILoader.load_index()
    objects = index.get("objects", {})
    related_objects = []
    for obj_name, obj_data in objects.items():
        file_path = obj_data.get("file", "")
        if index_key in file_path or (index_key == "itasca" and "/" not in file_path):
            related_objects.append(obj_name)

    object_note = ""
    if related_objects:
        obj_paths = [f"{module_path}.{obj}" for obj in related_objects]
        object_note = f"\nRelated Objects: {', '.join(obj_paths)}"

    content = f"""## {module_path}

{description}

Functions ({len(func_lines)}):
{chr(10).join(func_lines)}
{object_note}

Navigation:
- pfc_browse_python_api(api="{module_path}.<func>") for function doc
- pfc_browse_python_api() for root overview
"""

    return success_response(
        message=f"{module_path}: {len(func_lines)} functions",
        llm_content={"parts": [{"type": "text", "text": content}]},
        data={
            "level": "module",
            "module_path": module_path,
            "function_count": len(func_lines),
            "functions": [f.get("name") if isinstance(f, dict) else f for f in functions]
        }
    )


def _browse_function(module_path: str, func_name: str) -> Dict[str, Any]:
    """Browse a specific function documentation."""
    index_key = _path_to_index_key(module_path)
    func_doc = APILoader.load_function(index_key, func_name)

    if not func_doc:
        # Fallback to module level
        return _browse_module_with_error(module_path, f"Function '{func_name}' not found in {module_path}")

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


def _browse_object(module_path: str, object_name: str, display_name: str = None) -> Dict[str, Any]:
    """Browse an object - list its method groups.

    Args:
        module_path: Module path (e.g., "itasca.ball" or "itasca")
        object_name: Actual object name in index (e.g., "Ball", "Contact")
        display_name: Display name for Contact types (e.g., "BallBallContact")
    """
    object_doc = APILoader.load_object(object_name)

    if not object_doc:
        return error_response(f"Object not found: {object_name}")

    # Use display_name if provided (for Contact type aliases)
    shown_name = display_name or object_name
    description = object_doc.get("description", "")
    note = object_doc.get("note", "")
    method_groups = object_doc.get("method_groups", {})
    methods = object_doc.get("methods", [])

    # Build method groups or list
    method_lines = []
    if method_groups:
        for group_name, group_methods in method_groups.items():
            if isinstance(group_methods, list):
                method_list = ", ".join(group_methods[:5])
                if len(group_methods) > 5:
                    method_list += f", ... (+{len(group_methods)-5})"
                method_lines.append(f"- {group_name}: {method_list}")
            else:
                method_lines.append(f"- {group_name}: {group_methods}")
    elif methods:
        # Methods can be list of strings or list of dicts
        method_names = []
        for m in methods:
            if isinstance(m, dict):
                method_names.append(m.get("name", str(m)))
            else:
                method_names.append(str(m))
        # List methods in chunks
        for i in range(0, len(method_names), 5):
            chunk = method_names[i:i+5]
            method_lines.append(f"  {', '.join(chunk)}")

    note_text = f"\nNote: {note}" if note else ""
    full_path = f"{module_path}.{shown_name}"

    content = f"""## {full_path}

{description}
{note_text}

Method Groups:
{chr(10).join(method_lines)}

Navigation:
- pfc_browse_python_api(api="{full_path}.<method>") for method doc
- pfc_browse_python_api(api="{module_path}") for module overview
"""

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


def _browse_method(module_path: str, object_name: str, method_name: str, display_name: str = None) -> Dict[str, Any]:
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
        # Fallback to object level
        return _browse_object_with_error(
            module_path, object_name,
            f"Method '{method_name}' not found in {shown_name}"
        )

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
    """Handle error case by falling back to parent level."""
    error_msg = parsed.get("error", "Unknown error")
    fallback_path = parsed.get("fallback_path", "")

    if not fallback_path:
        # Fall back to root
        result = _browse_root()
        # Prepend error message
        if result.get("status") == "success":
            llm_content = result.get("llm_content", {})
            parts = llm_content.get("parts", [])
            if parts:
                parts[0]["text"] = f"Error: {error_msg}\n\n{parts[0]['text']}"
        return result
    else:
        # Try to browse fallback path
        normalized = _normalize_api_path(fallback_path)
        if not normalized or normalized == "itasca":
            result = _browse_root()
        else:
            # Re-parse and browse
            re_parsed = _parse_api_path(normalized)
            if re_parsed["type"] == "module":
                result = _browse_module(re_parsed["module_path"])
            elif re_parsed["type"] == "object":
                result = _browse_object(re_parsed["module_path"], re_parsed["name"])
            else:
                result = _browse_root()

        # Prepend error message
        if result.get("status") == "success":
            llm_content = result.get("llm_content", {})
            parts = llm_content.get("parts", [])
            if parts:
                parts[0]["text"] = f"Error: {error_msg}\n\n{parts[0]['text']}"
        return result


def _browse_module_with_error(module_path: str, error_msg: str) -> Dict[str, Any]:
    """Browse module with error message prepended."""
    result = _browse_module(module_path)
    if result.get("status") == "success":
        llm_content = result.get("llm_content", {})
        parts = llm_content.get("parts", [])
        if parts:
            parts[0]["text"] = f"Error: {error_msg}\n\n{parts[0]['text']}"
    return result


def _browse_object_with_error(module_path: str, object_name: str, error_msg: str) -> Dict[str, Any]:
    """Browse object with error message prepended."""
    result = _browse_object(module_path, object_name)
    if result.get("status") == "success":
        llm_content = result.get("llm_content", {})
        parts = llm_content.get("parts", [])
        if parts:
            parts[0]["text"] = f"Error: {error_msg}\n\n{parts[0]['text']}"
    return result
