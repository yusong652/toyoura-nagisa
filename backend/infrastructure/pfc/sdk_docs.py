"""PFC Python SDK documentation query utilities.

This module provides core functionality for searching, loading, and formatting
PFC Python SDK API documentation. It is independent of any presentation layer
(MCP, REST API, CLI) and can be used by any module that needs to access
PFC API reference information.

Core capabilities:
- Keyword-based API search
- API documentation loading
- LLM-friendly markdown formatting
"""

import json
from typing import Optional, Dict, Any, Tuple

from backend.infrastructure.pfc.config import PFC_DOCS_SOURCE, SDK_SEARCH_TOP_N

# Contact type aliases - all contact types share the same interface
# Official API: itasca.BallBallContact, itasca.BallFacetContact, etc.
# Internal docs: Contact.json (shared interface)
CONTACT_TYPES = [
    "BallBallContact",
    "BallFacetContact",
    "BallPebbleContact",
    "PebblePebbleContact",
    "PebbleFacetContact"
]

# Object class to module mapping
# Maps class names to their parent module names
# Format: "ClassName" -> "module_name"
# Official path: itasca.{module}.{Class}.{method}
CLASS_TO_MODULE = {
    "Ball": "ball",
    "Clump": "clump",
    "Contact": "contact",  # Generic contact (handled separately)
    "Measure": "measure",
    "Wall": "wall",
    "Facet": "wall",  # Facet is under wall module
    "Pebble": "clump",  # Pebble is under clump module
}


def load_index() -> Dict[str, Any]:
    """Load the index file for fast API lookups.

    Returns:
        Dict containing:
            - quick_ref: Direct API name to file reference mapping
            - keywords: Keyword to API list mapping
            - fallback_hints: Suggestions when SDK doesn't support operation

    Raises:
        FileNotFoundError: If index.json doesn't exist
    """
    index_path = PFC_DOCS_SOURCE / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"Index file not found: {index_path}")

    with open(index_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_all_keywords() -> Dict[str, list]:
    """Load keywords from all modules.

    Loads keywords from:
    - itasca_keywords.json (top-level module)
    - modules/*/keywords.json (sub-modules like ball, contact, etc.)

    Returns:
        Dict mapping keywords to API names
    """
    all_keywords = {}

    # Load itasca keywords
    itasca_keywords_path = PFC_DOCS_SOURCE / "itasca_keywords.json"
    if itasca_keywords_path.exists():
        with open(itasca_keywords_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            all_keywords.update(data.get("keywords", {}))

    # Load keywords from all modules
    modules_dir = PFC_DOCS_SOURCE / "modules"
    if modules_dir.exists():
        for module_dir in modules_dir.iterdir():
            if module_dir.is_dir():
                keywords_file = module_dir / "keywords.json"
                if keywords_file.exists():
                    with open(keywords_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        all_keywords.update(data.get("keywords", {}))

    return all_keywords


def search_by_path(api_path: str) -> Optional[Tuple[str, Optional[Dict[str, Any]]]]:
    """Search for API by exact path matching with Contact type support.

    This function handles queries that look like API paths and tries to match them
    from the index's quick_ref. For Contact types, it intelligently maps official
    paths to internal documentation while preserving the original type information.

    Supports:
    - Module functions: "itasca.ball.create", "itasca.measure.count"
    - Object methods: "Ball.vel", "Measure.pos"
    - Contact types (with aliases):
      * "itasca.BallBallContact.gap" → Contact.gap + metadata
      * "BallBallContact.gap" → Contact.gap + metadata (partial path)

    Args:
        api_path: API path string, e.g., "itasca.measure.count" or "BallBallContact.gap"

    Returns:
        Tuple of (matched_api_name, metadata) if found, None otherwise.
        - matched_api_name: Internal API name (e.g., "Contact.gap")
        - metadata: Dict with contact type info if applicable, None for regular APIs

    Examples:
        >>> search_by_path("itasca.measure.count")
        ("itasca.measure.count", None)
        >>> search_by_path("BallBallContact.gap")
        ("Contact.gap", {"contact_type": "BallBallContact", "original_query": "BallBallContact.gap"})
        >>> search_by_path("ball.vel")  # Case-insensitive
        ("Ball.vel", None)
    """
    api_path_stripped = api_path.strip()

    # Quick validation: must contain a dot
    if '.' not in api_path_stripped:
        return None

    # Check for Contact type queries first (case-insensitive)
    # Supports: "itasca.BallBallContact.gap", "BallBallContact.gap", "ballballcontact.gap"
    parts = api_path_stripped.split('.')
    parts_lower = [p.lower() for p in parts]

    for contact_type in CONTACT_TYPES:
        contact_type_lower = contact_type.lower()

        # Check if this contact type appears in the path (case-insensitive)
        if contact_type_lower in parts_lower:
            # Find method name after the contact type
            contact_idx = parts_lower.index(contact_type_lower)
            if contact_idx + 1 < len(parts):
                method_name = parts[contact_idx + 1]
                internal_path = f"Contact.{method_name}"

                # Verify this method exists in Contact (case-insensitive)
                index = load_index()
                quick_ref = index.get("quick_ref", {})

                # Try exact match first
                if internal_path in quick_ref:
                    return (
                        internal_path,
                        {
                            "contact_type": contact_type,
                            "original_query": api_path_stripped,
                            "all_contact_types": CONTACT_TYPES
                        }
                    )

                # Try case-insensitive match for method name
                internal_path_lower = internal_path.lower()
                for api_name in quick_ref.keys():
                    if api_name.lower() == internal_path_lower:
                        return (
                            api_name,
                            {
                                "contact_type": contact_type,
                                "original_query": api_path_stripped,
                                "all_contact_types": CONTACT_TYPES
                            }
                        )

    # Regular API lookup (non-Contact types)
    index = load_index()
    quick_ref = index.get("quick_ref", {})

    # Try exact match first (case-sensitive)
    if api_path_stripped in quick_ref:
        return (api_path_stripped, None)

    # Try case-insensitive match for user convenience
    api_path_lower = api_path_stripped.lower()
    for api_name in quick_ref.keys():
        if api_name.lower() == api_path_lower:
            return (api_name, None)  # Return the correctly-cased version

    return None


def search_by_keyword(query: str, top_n: int = SDK_SEARCH_TOP_N) -> list[tuple[str, int]]:
    """Search for API based on natural language keywords.

    Uses flexible word matching: if all words in a keyword are present
    in the query, it's considered a match. Returns top-N matches sorted
    by word overlap score (descending).

    Args:
        query: Natural language query like "create a ball" or "list all balls"
        top_n: Maximum number of results to return (default: 3)

    Returns:
        List of (api_name, score) tuples sorted by score (highest first).
        Empty list if no matches found.

    Examples:
        >>> search_by_keyword("create a ball")
        [("itasca.ball.create", 2)]
        >>> search_by_keyword("ball velocity")
        [("Ball.vel", 2), ("Ball.vel_set", 2), ("Ball.vel_spin", 2)]
        >>> search_by_keyword("cubic packing")
        []
    """
    keywords = load_all_keywords()
    query_lower = query.lower()

    # Try keyword match with flexible word matching
    query_words = set(query_lower.split())
    matches = []  # List of (api_name, score) tuples

    for keyword, apis in keywords.items():
        keyword_words = set(keyword.split())
        # Calculate how many keyword words match
        matching_words = keyword_words & query_words
        score = len(matching_words)

        # If all keyword words are in query, it's a valid match
        if matching_words == keyword_words and score > 0:
            # Add all APIs associated with this keyword
            for api_name in apis:
                matches.append((api_name, score))

    # Sort by score (descending), then by API name (for stability)
    matches.sort(key=lambda x: (-x[1], x[0]))

    # Return top-N unique matches
    seen = set()
    unique_matches = []
    for api_name, score in matches:
        if api_name not in seen:
            seen.add(api_name)
            unique_matches.append((api_name, score))
            if len(unique_matches) >= top_n:
                break

    return unique_matches


def search_api(query: str, top_n: int = SDK_SEARCH_TOP_N) -> list[tuple[str, int, Optional[Dict[str, Any]]]]:
    """Smart API search with automatic path vs keyword detection.

    This is the main search entry point that intelligently routes to either
    path-based or keyword-based search:

    1. **Path matching**: If query looks like an API path (contains "."), tries exact
       path match first. Handles Contact type aliases automatically.
    2. **Keyword matching**: Falls back to natural language keyword search.

    Args:
        query: Either an API path ("itasca.measure.count", "BallBallContact.gap")
               or natural language query ("measure count", "create ball")
        top_n: Maximum number of results to return (default: 3)

    Returns:
        List of (api_name, score, metadata) tuples sorted by score (highest first).
        - api_name: Internal API name (e.g., "Contact.gap" for contact methods)
        - score: 999 for path matches, word overlap scores for keyword matches
        - metadata: Dict with contact_type info if applicable, None otherwise

    Examples:
        >>> search_api("itasca.measure.count")
        [("itasca.measure.count", 999, None)]
        >>> search_api("BallBallContact.gap")
        [("Contact.gap", 999, {"contact_type": "BallBallContact", ...})]
        >>> search_api("measure count")
        [("itasca.measure.count", 2, None)]
    """
    query_stripped = query.strip()

    # Strategy 1: Try path-based search first if query contains a dot
    # This handles both "itasca.xxx.yyy" and "ClassName.method" patterns
    if '.' in query_stripped:
        result = search_by_path(query_stripped)
        if result:
            api_name, metadata = result
            return [(api_name, 999, metadata)]  # High score for exact path match

    # Strategy 2: Fall back to keyword-based search
    keyword_results = search_by_keyword(query_stripped, top_n=top_n)
    # Add None metadata for keyword results
    return [(api_name, score, None) for api_name, score in keyword_results]


def load_api_doc(api_name: str) -> Optional[Dict[str, Any]]:
    """Load documentation for a specific API.

    Args:
        api_name: Full API name like "itasca.ball.create"

    Returns:
        API documentation dict with fields:
            - signature: Function signature
            - description: Detailed description
            - parameters: List of parameter definitions
            - returns: Return value information
            - examples: Usage examples
            - limitations: Known limitations (optional)
            - fallback_commands: Alternative commands (optional)
            - best_practices: Recommended practices (optional)
            - notes: Additional notes (optional)
            - see_also: Related APIs (optional)

        Returns None if API not found.
    """
    index = load_index()

    # Get file reference from index
    ref = index["quick_ref"].get(api_name)
    if not ref:
        return None

    # Parse file path and anchor
    file_name, anchor = ref.split('#')
    doc_path = PFC_DOCS_SOURCE / file_name

    if not doc_path.exists():
        return None

    with open(doc_path, 'r', encoding='utf-8') as f:
        doc = json.load(f)

    # Find the specific function or method
    # Check if it's an object file (contains "methods") or module file (contains "functions")
    if "methods" in doc:
        # Object method file (e.g., ball_object.json)
        for method in doc["methods"]:
            if method["name"] == anchor:
                return method
    elif "functions" in doc:
        # Module function file (e.g., ball.json)
        for func in doc["functions"]:
            if func["name"] == anchor:
                return func

    return None


def format_api_signature(api_name: str) -> Optional[str]:
    """Format API signature as brief one-liner for quick reference.

    Args:
        api_name: Full API name like "itasca.ball.create"

    Returns:
        Brief signature string like "itasca.ball.create(radius, pos=None) - Create a new ball"
        Returns None if API not found.

    Examples:
        >>> format_api_signature("Ball.vel")
        "Ball.vel() -> tuple[float, float, float] - Get ball velocity vector"
    """
    api_doc = load_api_doc(api_name)
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

    return f"`{api_doc['signature']}`{return_info} - {brief_desc}"


def format_api_doc(api_doc: Dict[str, Any], api_name: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Format API documentation as LLM-friendly markdown with Contact type support.

    Generates structured markdown with clear sections for LLM consumption,
    including signature, parameters, examples, limitations, and best practices.

    For Contact types, returns official API path (e.g., "itasca.BallBallContact.gap")
    instead of internal path ("Contact.gap") and includes type availability info.

    Args:
        api_doc: API documentation dictionary from load_api_doc()
        api_name: Internal API name (e.g., "itasca.ball.create" or "Contact.gap")
        metadata: Optional metadata dict with contact_type info for Contact methods

    Returns:
        Formatted markdown string

    Example output structure (Contact type):
        # itasca.BallBallContact.gap

        **Available for**: BallBallContact, BallFacetContact, PebblePebbleContact, ...

        **Signature**: `contact.gap() -> float`

        Get the gap between contact entities...

    Example output structure (regular):
        # itasca.ball.create

        **Signature**: `ball.create(...)`

        Creates a new ball in the simulation...
    """
    lines = []

    # Determine the display path (official API path)
    # Three cases:
    # 1. Contact types: itasca.{ContactType}.{method}
    # 2. Object methods: itasca.{module}.{Class}.{method}
    # 3. Module functions: itasca.{module}.{function}

    display_path = api_name  # Default to internal path

    if metadata and 'contact_type' in metadata:
        # Case 1: Contact type
        contact_type = metadata['contact_type']
        method_name = api_name.split('.')[-1]  # Extract method from "Contact.gap"
        display_path = f"itasca.{contact_type}.{method_name}"

        lines.append(f"# {display_path}")
        lines.append("")

        # Add type availability info
        all_types = metadata.get('all_contact_types', CONTACT_TYPES)
        lines.append(f"**Available for**: {', '.join(all_types)}")
        lines.append("")

    elif '.' in api_name and not api_name.startswith('itasca.'):
        # Case 2: Object method (e.g., "Ball.vel", "Wall.vel")
        class_name = api_name.split('.')[0]
        method_name = api_name.split('.')[-1]

        if class_name in CLASS_TO_MODULE:
            module_name = CLASS_TO_MODULE[class_name]
            display_path = f"itasca.{module_name}.{api_name}"  # itasca.ball.Ball.vel

        lines.append(f"# {display_path}")
        lines.append("")

    else:
        # Case 3: Module function (already has full path like "itasca.ball.create")
        lines.append(f"# {display_path}")
        lines.append("")

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
            lines.append(f"- **`{param['name']}`** ({param['type']}, {required}): {param['description']}")
        lines.append("")

    # Returns
    if api_doc.get('returns'):
        ret = api_doc['returns']
        lines.append(f"## Returns")
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

    # Limitations (IMPORTANT - guides to command fallback)
    if api_doc.get('limitations'):
        lines.append("## Limitations")
        lines.append(api_doc['limitations'])
        lines.append("")

        if api_doc.get('fallback_commands'):
            lines.append(f"**When to use commands instead**: {', '.join(api_doc['fallback_commands'])}")
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
