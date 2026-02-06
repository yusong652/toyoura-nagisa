"""
Antigravity tool managers.
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend.config.dev import get_dev_config
from backend.infrastructure.llm.base.tool_manager import BaseToolManager
from backend.infrastructure.llm.shared.utils.tool_schema import ToolSchema

UNSUPPORTED_CONSTRAINTS = {
    "minLength",
    "maxLength",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "pattern",
    "minItems",
    "maxItems",
    "format",
    "default",
    "examples",
}

UNSUPPORTED_KEYWORDS = UNSUPPORTED_CONSTRAINTS | {
    "$schema",
    "$defs",
    "definitions",
    "const",
    "$ref",
    "additionalProperties",
    "propertyNames",
    "title",
    "$id",
    "$comment",
    "propertyOrdering",
    "nullable",
}


def clean_json_schema_for_antigravity(schema: Any) -> Dict[str, Any]:
    def normalize_properties_map(node: Any) -> Any:
        if isinstance(node, list):
            return [normalize_properties_map(item) for item in node]
        if not isinstance(node, dict):
            return node

        result: Dict[str, Any] = {}
        for key, value in node.items():
            if key == "properties" and isinstance(value, list):
                props: Dict[str, Any] = {}
                for entry in value:
                    if not isinstance(entry, dict):
                        continue
                    prop_key = entry.get("key") or entry.get("name")
                    prop_value = entry.get("value") if "value" in entry else entry.get("schema")
                    if isinstance(prop_key, str) and prop_key:
                        props[prop_key] = normalize_properties_map(prop_value)
                result[key] = props
            else:
                result[key] = normalize_properties_map(value)

        return result

    def append_description_hint(node: Dict[str, Any], hint: str) -> Dict[str, Any]:
        if not hint:
            return node
        existing = node.get("description")
        if isinstance(existing, str) and existing:
            node["description"] = f"{existing} ({hint})"
        else:
            node["description"] = hint
        return node

    def convert_refs_to_hints(node: Any) -> Any:
        if isinstance(node, list):
            return [convert_refs_to_hints(item) for item in node]
        if not isinstance(node, dict):
            return node
        ref_value = node.get("$ref")
        if isinstance(ref_value, str):
            def_name = ref_value.split("/")[-1] if "/" in ref_value else ref_value
            description = node.get("description")
            hint = f"See: {def_name}"
            result: Dict[str, Any] = {"type": "object"}
            if isinstance(description, str) and description:
                result["description"] = f"{description} ({hint})"
            else:
                result["description"] = hint
            return result
        return {key: convert_refs_to_hints(value) for key, value in node.items()}

    def convert_const_to_enum(node: Any) -> Any:
        if isinstance(node, list):
            return [convert_const_to_enum(item) for item in node]
        if not isinstance(node, dict):
            return node
        result: Dict[str, Any] = {}
        for key, value in node.items():
            if key == "const" and "enum" not in node:
                result["enum"] = [value]
                continue
            result[key] = convert_const_to_enum(value)
        return result

    def add_enum_hints(node: Any) -> Any:
        if isinstance(node, list):
            return [add_enum_hints(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = dict(node)
        enum_values = result.get("enum")
        if isinstance(enum_values, list) and 1 < len(enum_values) <= 10:
            hint = ", ".join(str(item) for item in enum_values)
            result = append_description_hint(result, f"Allowed: {hint}")
        for key, value in list(result.items()):
            if key != "enum" and isinstance(value, (dict, list)):
                result[key] = add_enum_hints(value)
        return result

    def add_additional_properties_hints(node: Any) -> Any:
        if isinstance(node, list):
            return [add_additional_properties_hints(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = dict(node)
        if result.get("additionalProperties") is False:
            result = append_description_hint(result, "No extra properties allowed")
        for key, value in list(result.items()):
            if key != "additionalProperties" and isinstance(value, (dict, list)):
                result[key] = add_additional_properties_hints(value)
        return result

    def move_constraints_to_description(node: Any) -> Any:
        if isinstance(node, list):
            return [move_constraints_to_description(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = dict(node)
        for constraint in UNSUPPORTED_CONSTRAINTS:
            if constraint in result and not isinstance(result[constraint], (dict, list)):
                result = append_description_hint(result, f"{constraint}: {result[constraint]}")
        for key, value in list(result.items()):
            if isinstance(value, (dict, list)):
                result[key] = move_constraints_to_description(value)
        return result

    def merge_all_of(node: Any) -> Any:
        if isinstance(node, list):
            return [merge_all_of(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = dict(node)
        all_of = result.pop("allOf", None)
        if isinstance(all_of, list) and all_of:
            merged: Dict[str, Any] = {}
            for entry in all_of:
                entry_clean = merge_all_of(entry)
                if not isinstance(entry_clean, dict):
                    continue
                for key, value in entry_clean.items():
                    if key == "required" and isinstance(value, list):
                        existing = merged.get("required")
                        if isinstance(existing, list):
                            merged["required"] = list(dict.fromkeys(existing + value))
                        else:
                            merged["required"] = value
                    elif key == "properties" and isinstance(value, dict):
                        props = merged.get("properties")
                        if isinstance(props, dict):
                            props.update(value)
                            merged["properties"] = props
                        else:
                            merged["properties"] = dict(value)
                    else:
                        merged[key] = value
            merged.update(result)
            result = merged
        for key, value in list(result.items()):
            if isinstance(value, (dict, list)):
                result[key] = merge_all_of(value)
        return result

    def try_merge_enum_from_union(options: List[Any]) -> "List[str] | None":
        """Detect enum patterns in anyOf/oneOf and merge into a single enum list.

        Handles:
          anyOf: [{ const: "a" }, { const: "b" }]
          anyOf: [{ enum: ["a"] }, { enum: ["b"] }]
          anyOf: [{ type: "string", const: "a" }, ...]
        """
        if not options:
            return None
        enum_values: List[str] = []
        for option in options:
            if not isinstance(option, dict):
                return None
            if "const" in option:
                enum_values.append(str(option["const"]))
            elif isinstance(option.get("enum"), list) and option["enum"]:
                for val in option["enum"]:
                    enum_values.append(str(val))
            elif option.get("properties") or option.get("items") or option.get("anyOf") or option.get("oneOf") or option.get("allOf"):
                return None
            elif option.get("type") and "const" not in option and "enum" not in option:
                return None
            else:
                return None
        return enum_values if enum_values else None

    def score_schema_option(option: Any) -> int:
        if not isinstance(option, dict):
            return 0
        if option.get("type") == "object" or "properties" in option:
            return 3
        if option.get("type") == "array" or "items" in option:
            return 2
        if option.get("type") and option.get("type") != "null":
            return 1
        return 0

    def flatten_any_of_one_of(node: Any) -> Any:
        if isinstance(node, list):
            return [flatten_any_of_one_of(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = dict(node)
        for union_key in ("anyOf", "oneOf"):
            union_value = result.get(union_key)
            if not isinstance(union_value, list) or not union_value:
                continue

            parent_desc = result.get("description", "")

            # Phase 1: detect enum patterns like anyOf: [{const:"a"}, {const:"b"}]
            merged_enum = try_merge_enum_from_union(union_value)
            if merged_enum is not None:
                result.pop(union_key, None)
                result["type"] = "string"
                result["enum"] = merged_enum
                if parent_desc:
                    result["description"] = parent_desc
                continue

            # Phase 2: detect Optional[T] pattern — anyOf: [{type: T}, {type: "null"}]
            non_null = [o for o in union_value if isinstance(o, dict) and o.get("type") != "null"]
            has_null = any(isinstance(o, dict) and o.get("type") == "null" for o in union_value)

            if has_null and len(non_null) == 1:
                selected = flatten_any_of_one_of(non_null[0])
                if not isinstance(selected, dict):
                    selected = {"type": "string"}
                if parent_desc:
                    child_desc = selected.get("description", "")
                    if child_desc and child_desc != parent_desc:
                        selected["description"] = f"{parent_desc} ({child_desc})"
                    elif not child_desc:
                        selected["description"] = parent_desc
                selected = append_description_hint(selected, "nullable")
                result.pop(union_key, None)
                result.pop("description", None)
                result.update(selected)
                continue

            # Phase 3: general multi-type union — score each option and pick the best
            best_idx = 0
            best_score = -1
            all_types: List[str] = []
            for i, candidate in enumerate(union_value):
                s = score_schema_option(candidate)
                t = candidate.get("type", "unknown") if isinstance(candidate, dict) else "unknown"
                if t:
                    all_types.append(str(t))
                if s > best_score:
                    best_score = s
                    best_idx = i

            selected = flatten_any_of_one_of(union_value[best_idx])
            if not isinstance(selected, dict):
                selected = {"type": "string"}

            if parent_desc:
                child_desc = selected.get("description", "")
                if child_desc and child_desc != parent_desc:
                    selected["description"] = f"{parent_desc} ({child_desc})"
                elif not child_desc:
                    selected["description"] = parent_desc

            unique_types = list(dict.fromkeys(all_types))
            non_null_types = [t for t in unique_types if t != "null"]
            if len(non_null_types) > 1:
                selected = append_description_hint(selected, f"Accepts: {' | '.join(non_null_types)}")
            if has_null:
                selected = append_description_hint(selected, "nullable")

            result.pop(union_key, None)
            result.pop("description", None)
            result.update(selected)

        for key, value in list(result.items()):
            if isinstance(value, (dict, list)):
                result[key] = flatten_any_of_one_of(value)
        return result

    def flatten_type_arrays(node: Any) -> Any:
        if isinstance(node, list):
            return [flatten_type_arrays(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = dict(node)
        node_type = result.get("type")
        if isinstance(node_type, list):
            types_list = [t for t in node_type if isinstance(t, str)]
            types_list = [t.lower() for t in types_list]
            has_null = "null" in types_list
            non_null = [t for t in types_list if t != "null"]
            first_type = non_null[0] if non_null else "string"
            result["type"] = first_type
            if len(non_null) > 1:
                result = append_description_hint(result, f"Accepts: {' | '.join(non_null)}")
            if has_null:
                result = append_description_hint(result, "nullable")
        elif isinstance(node_type, str):
            result["type"] = node_type.lower()

        for key, value in list(result.items()):
            if isinstance(value, (dict, list)):
                result[key] = flatten_type_arrays(value)
        return result

    def remove_unsupported_keywords(node: Any, inside_properties: bool = False) -> Any:
        if isinstance(node, list):
            return [remove_unsupported_keywords(item, False) for item in node]
        if not isinstance(node, dict):
            return node
        result: Dict[str, Any] = {}
        for key, value in node.items():
            if not inside_properties and key in UNSUPPORTED_KEYWORDS:
                continue
            if isinstance(value, (dict, list)):
                if key == "properties" and isinstance(value, dict):
                    props: Dict[str, Any] = {}
                    for prop_name, prop_schema in value.items():
                        props[prop_name] = remove_unsupported_keywords(prop_schema, False)
                    result[key] = props
                else:
                    result[key] = remove_unsupported_keywords(value, False)
            else:
                result[key] = value
        return result

    def cleanup_required_fields(node: Any) -> Any:
        if isinstance(node, list):
            return [cleanup_required_fields(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = dict(node)
        properties = result.get("properties")
        required = result.get("required")
        if isinstance(required, list) and isinstance(properties, dict):
            valid_required = [item for item in required if item in properties]
            if not valid_required:
                result.pop("required", None)
            else:
                result["required"] = valid_required
        for key, value in list(result.items()):
            if isinstance(value, (dict, list)):
                result[key] = cleanup_required_fields(value)
        return result

    def add_empty_schema_placeholder(node: Any) -> Any:
        if isinstance(node, list):
            return [add_empty_schema_placeholder(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = dict(node)
        node_type = result.get("type")
        properties = result.get("properties")
        if (node_type == "object" or isinstance(properties, dict)) and (not properties):
            result["type"] = "object"
            result["properties"] = {
                "_placeholder": {
                    "type": "boolean",
                    "description": "Placeholder. Always pass true.",
                }
            }
            result["required"] = ["_placeholder"]
        for key, value in list(result.items()):
            if isinstance(value, (dict, list)):
                result[key] = add_empty_schema_placeholder(value)
        return result

    def inline_defs_refs(node: Any, defs: Dict[str, Any]) -> Any:
        """Resolve $ref by inlining definitions from $defs/definitions.

        Turns  {"$ref": "#/$defs/CutPlane"}
        into   the full CutPlane schema with origin/normal properties.
        Unresolvable refs are left for convert_refs_to_hints to handle.
        """
        if isinstance(node, list):
            return [inline_defs_refs(item, defs) for item in node]
        if not isinstance(node, dict):
            return node

        ref_value = node.get("$ref")
        if isinstance(ref_value, str):
            parts = ref_value.split("/")
            if len(parts) >= 3 and parts[-2] in ("$defs", "definitions"):
                def_name = parts[-1]
                resolved = defs.get(def_name)
                if isinstance(resolved, dict):
                    result = inline_defs_refs(dict(resolved), defs)
                    # Preserve description from the ref site
                    desc = node.get("description")
                    if isinstance(desc, str) and desc and "description" not in result:
                        result["description"] = desc
                    return result
            # Unresolvable ref — leave for convert_refs_to_hints
            return node

        return {key: inline_defs_refs(value, defs) for key, value in node.items()}

    # Extract $defs before pipeline (they'll be stripped by remove_unsupported_keywords)
    top_defs: Dict[str, Any] = {}
    if isinstance(schema, dict):
        top_defs = schema.get("$defs") or schema.get("definitions") or {}

    processed: Any = normalize_properties_map(schema)
    if top_defs:
        processed = inline_defs_refs(processed, top_defs)
    processed = convert_refs_to_hints(processed)
    processed = convert_const_to_enum(processed)
    processed = add_enum_hints(processed)
    processed = add_additional_properties_hints(processed)
    processed = move_constraints_to_description(processed)
    processed = merge_all_of(processed)
    processed = flatten_any_of_one_of(processed)
    processed = flatten_type_arrays(processed)
    processed = remove_unsupported_keywords(processed)
    processed = cleanup_required_fields(processed)
    processed = add_empty_schema_placeholder(processed)

    if isinstance(processed, dict):
        return processed

    return {"type": "object", "properties": {"_placeholder": {"type": "boolean"}}, "required": ["_placeholder"]}


class ClaudeAntigravityToolManager(BaseToolManager):
    """Tool manager that preserves JSON schema semantics for Claude Antigravity."""

    async def get_function_call_schemas(
        self, session_id: str, agent_profile: str = "pfc_expert"
    ) -> List[Dict[str, Any]]:
        tools_dict = await self.get_standardized_tools(session_id, agent_profile)

        if get_dev_config().debug_mode:
            print(
                "[DEBUG] GoogleClaudeAntigravityToolManager: "
                f"agent_profile={agent_profile}, tools_found={list(tools_dict.keys())}"
            )

        if not tools_dict:
            return []

        function_declarations: List[Dict[str, Any]] = []
        for tool_schema in tools_dict.values():
            if not isinstance(tool_schema, ToolSchema):
                continue
            raw_schema = tool_schema.inputSchema.model_dump(exclude_none=True, by_alias=True)
            cleaned_schema = clean_json_schema_for_antigravity(raw_schema)

            function_declarations.append(
                {
                    "name": tool_schema.name,
                    "description": tool_schema.description or "No description available",
                    "parameters": cleaned_schema,
                }
            )

        if not function_declarations:
            return []

        return [{"functionDeclarations": function_declarations}]


def _format_type_hint(prop_schema: Any) -> str:
    """Format a concise type hint from a property schema."""
    if not isinstance(prop_schema, dict):
        return "unknown"
    t = prop_schema.get("type", "")
    if t == "array":
        items = prop_schema.get("items")
        item_type = _format_type_hint(items) if isinstance(items, dict) else "any"
        return f"array<{item_type}>"
    if t == "object":
        return "object"
    enum_vals = prop_schema.get("enum")
    if isinstance(enum_vals, list) and enum_vals:
        return f"enum[{','.join(str(v) for v in enum_vals)}]"
    return str(t) if t else "any"


def inject_parameter_signatures(
    tools: List[Dict[str, Any]],
    prompt_template: str = "\n\n⚠️ STRICT PARAMETERS: {params}.",
) -> List[Dict[str, Any]]:
    """Inject parameter type signatures into tool descriptions.

    For each functionDeclaration, appends a line like:
      ⚠️ STRICT PARAMETERS: url (string, REQUIRED), prompt (string, REQUIRED).
    """
    if not tools:
        return tools

    result: List[Dict[str, Any]] = []
    for tool in tools:
        declarations = tool.get("functionDeclarations")
        if not isinstance(declarations, list):
            result.append(tool)
            continue

        new_declarations: List[Dict[str, Any]] = []
        for decl in declarations:
            if not isinstance(decl, dict):
                new_declarations.append(decl)
                continue

            desc = decl.get("description", "")
            if "STRICT PARAMETERS:" in desc:
                new_declarations.append(decl)
                continue

            schema = decl.get("parameters") or {}
            if not isinstance(schema, dict):
                new_declarations.append(decl)
                continue

            properties = schema.get("properties")
            if not isinstance(properties, dict) or not properties:
                new_declarations.append(decl)
                continue

            required = schema.get("required") or []

            param_parts: List[str] = []
            for prop_name, prop_data in properties.items():
                type_hint = _format_type_hint(prop_data)
                is_required = prop_name in required
                suffix = ", REQUIRED" if is_required else ""
                param_parts.append(f"{prop_name} ({type_hint}{suffix})")

            sig = prompt_template.replace("{params}", ", ".join(param_parts))
            new_declarations.append({**decl, "description": (desc or "") + sig})

        result.append({**tool, "functionDeclarations": new_declarations})

    return result


def inject_tool_hardening_instruction(
    system_instruction: Dict[str, Any],
    instruction_text: str,
) -> Dict[str, Any]:
    """Prepend tool hardening instruction to system instruction parts.

    Mutates and returns the system_instruction dict.
    """
    if not instruction_text:
        return system_instruction

    parts = system_instruction.get("parts")
    if not isinstance(parts, list):
        system_instruction["parts"] = [{"text": instruction_text}]
        return system_instruction

    # Skip if already injected
    for part in parts:
        if isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str) and "CRITICAL TOOL USAGE INSTRUCTIONS" in text:
                return system_instruction

    parts.insert(0, {"text": instruction_text})
    return system_instruction
