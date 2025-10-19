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
from typing import Optional, Dict, Any

from backend.infrastructure.pfc.config import PFC_DOCS_SOURCE


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


def search_api(query: str) -> Optional[str]:
    """Search for API based on query keywords.

    Uses flexible word matching: if all words in a keyword are present
    in the query, it's considered a match. Returns the best match with
    highest word overlap.

    Args:
        query: Natural language query like "create a ball" or "list all balls"

    Returns:
        API name like "itasca.ball.create" or None if not found

    Examples:
        >>> search_api("create a ball")
        "itasca.ball.create"
        >>> search_api("list all balls")
        "itasca.ball.list"
        >>> search_api("cubic packing")
        None
    """
    keywords = load_all_keywords()
    query_lower = query.lower()

    # Try keyword match with flexible word matching
    query_words = set(query_lower.split())
    best_match = None
    best_score = 0

    for keyword, apis in keywords.items():
        keyword_words = set(keyword.split())
        # Calculate how many keyword words match
        matching_words = keyword_words & query_words
        score = len(matching_words)

        # If all keyword words are in query, it's a valid match
        if matching_words == keyword_words and score > best_score:
            best_match = apis[0]
            best_score = score

    return best_match


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


def format_api_doc(api_doc: Dict[str, Any], api_name: str) -> str:
    """Format API documentation as LLM-friendly markdown.

    Generates structured markdown with clear sections for LLM consumption,
    including signature, parameters, examples, limitations, and best practices.

    Args:
        api_doc: API documentation dictionary from load_api_doc()
        api_name: Full API name for reference (e.g., "itasca.ball.create")

    Returns:
        Formatted markdown string

    Example output structure:
        # itasca.ball.create

        **Signature**: `ball.create(...)`

        Creates a new ball in the simulation...

        ## Parameters
        - **`radius`** (float, **required**): Ball radius

        ## Returns
        **`Ball`**: The created ball object

        ## Examples
        ...
    """
    lines = []

    # Header
    lines.append(f"# {api_name}")
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
        lines.append("## ⚠️ Limitations")
        lines.append(api_doc['limitations'])
        lines.append("")

        if api_doc.get('fallback_commands'):
            lines.append(f"**When to use commands instead**: {', '.join(api_doc['fallback_commands'])}")
            lines.append("")

    # Best Practices
    if api_doc.get('best_practices'):
        lines.append("## 💡 Best Practices")
        for bp in api_doc['best_practices']:
            lines.append(f"- {bp}")
        lines.append("")

    # Notes
    if api_doc.get('notes'):
        lines.append("## 📝 Notes")
        for note in api_doc['notes']:
            lines.append(f"- {note}")
        lines.append("")

    # See Also
    if api_doc.get('see_also'):
        lines.append(f"**See Also**: {', '.join(api_doc['see_also'])}")
        lines.append("")

    return "\n".join(lines)
