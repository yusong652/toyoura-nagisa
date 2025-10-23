"""Path-based search strategy for exact API path matching.

This strategy handles queries that look like API paths (contain dots)
and attempts to match them exactly against the index.

Supports:
- Full paths: "itasca.ball.create"
- Partial paths: "Ball.vel"
- Contact types: "BallBallContact.gap" (with intelligent aliasing)
- Case-insensitive matching
"""

from typing import List, Dict, Any, Optional
from backend.infrastructure.pfc.python_api.models import SearchResult, SearchStrategy as StrategyEnum
from backend.infrastructure.pfc.shared.search.base import SearchStrategy
from backend.infrastructure.pfc.python_api.loader import DocumentationLoader
from backend.infrastructure.pfc.python_api.types.contact import ContactTypeResolver


class PathSearchStrategy(SearchStrategy):
    """Search by exact API path matching.

    This strategy is used when the query contains a dot character,
    indicating it's likely an API path (e.g., "itasca.ball.create").

    Features:
    - Exact path matching with case-insensitive fallback
    - Special handling for Contact types (maps aliases to shared interface)
    - High score (999) for exact matches
    """

    def can_handle(self, query: str) -> bool:
        """Path queries must contain a dot.

        Args:
            query: Search query string

        Returns:
            True if query contains '.' (path-like)

        Example:
            >>> strategy = PathSearchStrategy()
            >>> strategy.can_handle("itasca.ball.create")
            True
            >>> strategy.can_handle("create ball")
            False
        """
        return '.' in query.strip()

    def search(self, query: str, top_n: int = 3) -> List[SearchResult]:
        """Execute path-based search.

        Search priority:
        1. Check if query is a Contact type (special handling)
        2. Try exact path match (case-sensitive)
        3. Try case-insensitive match (user convenience)
        4. Try partial path match (e.g., "Ball.velocity" → "Ball.vel")

        Args:
            query: API path string (e.g., "itasca.ball.create")
            top_n: Maximum number of results (ignored, path search returns 0 or 1)

        Returns:
            List with single SearchResult if found, empty list otherwise

        Example:
            >>> strategy = PathSearchStrategy()
            >>> results = strategy.search("BallBallContact.gap")
            >>> results[0].api_name
            "Contact.gap"
            >>> results[0].metadata["contact_type"]
            "BallBallContact"
        """
        query_stripped = query.strip()
        index = DocumentationLoader.load_index()
        quick_ref = index.get("quick_ref", {})

        # Strategy 1: Check Contact types first
        # Contact types need special handling to map official names to internal docs
        if ContactTypeResolver.is_contact_query(query_stripped):
            contact_result = ContactTypeResolver.resolve(query_stripped, quick_ref)
            if contact_result:
                return [SearchResult(
                    api_name=contact_result.internal_path,
                    score=999,  # Exact match score
                    strategy=StrategyEnum.PATH,
                    metadata={
                        "contact_type": contact_result.contact_type,
                        "original_query": contact_result.original_query,
                        "all_contact_types": contact_result.all_types
                    }
                )]

        # Strategy 2: Regular path lookup (exact match)
        if query_stripped in quick_ref:
            metadata = self._build_contact_metadata(query_stripped)
            return [SearchResult(
                api_name=query_stripped,
                score=999,
                strategy=StrategyEnum.PATH,
                metadata=metadata
            )]

        # Strategy 3: Case-insensitive fallback
        # Helps users who don't remember exact casing
        query_lower = query_stripped.lower()
        for api_name in quick_ref.keys():
            if api_name.lower() == query_lower:
                metadata = self._build_contact_metadata(api_name)
                return [SearchResult(
                    api_name=api_name,  # Return correctly-cased version
                    score=999,
                    strategy=StrategyEnum.PATH,
                    metadata=metadata
                )]

        # Strategy 4: Partial path matching
        # Handles cases like "Ball.velocity" → "Ball.vel" or "Wall.position" → "Wall.pos"
        partial_match = self._partial_path_match(query_stripped, quick_ref)
        if partial_match:
            return partial_match

        return []

    def _partial_path_match(self, query: str, quick_ref: dict) -> List[SearchResult]:
        """Attempt partial path matching for attribute/method names.

        Handles common scenarios where users query with:
        - Full attribute names instead of abbreviations ("Ball.velocity" → "Ball.vel")
        - Alternative names for the same concept ("Wall.position" → "Wall.pos")
        - Contact type aliases ("BallBallContact.force" → "Contact.force_global")

        Matching rules:
        1. Class/module name must match (case-insensitive)
           - Special case: Contact type names are aliased to "Contact"
        2. Attribute name partial matching:
           - Prefix match (first 3+ chars): "vel" matches "velocity"
           - Substring match: one is contained in the other
        3. Returns best match with score 850 (lower than exact match)

        Args:
            query: Path query string (must contain '.')
            quick_ref: Index of available API paths

        Returns:
            List with single SearchResult if partial match found, empty list otherwise

        Example:
            >>> self._partial_path_match("Ball.velocity", quick_ref)
            [SearchResult(api_name="Ball.vel", score=850, ...)]
            >>> self._partial_path_match("ballballcontact.force", quick_ref)
            [SearchResult(api_name="Contact.force_global", score=850, ...)]
        """
        if '.' not in query:
            return []

        # Parse query into class/module part and attribute/method part
        parts = query.split('.')
        if len(parts) < 2:
            return []

        # Handle both "Class.attr" and "module.Class.attr" patterns
        class_part = parts[-2].lower()  # Second-to-last part (Class name)
        attr_query = parts[-1].lower()  # Last part (attribute/method name)

        # Track if this is a Contact type query (for metadata)
        contact_type_match = None
        if ContactTypeResolver.is_contact_query(query):
            from backend.infrastructure.pfc.python_api.types.contact import CONTACT_TYPES
            for ct in CONTACT_TYPES:
                if ct.lower() == class_part:
                    contact_type_match = ct  # Remember original contact type
                    break
            # NOTE: We no longer map class_part to "contact" because the index
            # has been expanded with actual Contact type names (BallBallContact, etc.)

        # Collect candidates with match quality scores
        candidates = []

        for api_name in quick_ref.keys():
            api_parts = api_name.split('.')
            if len(api_parts) < 2:
                continue

            api_class = api_parts[-2].lower()  # Class/module in API
            api_attr = api_parts[-1].lower()  # Attribute/method in API

            # Class name must match (exact or case-insensitive)
            if api_class != class_part:
                continue

            # Calculate attribute match quality
            match_score = self._calculate_attr_match_score(attr_query, api_attr)

            if match_score > 0:
                candidates.append((api_name, match_score))

        # Return best match if any candidates found
        if candidates:
            # Sort by match score (descending)
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_match = candidates[0]

            # Build metadata
            metadata = {
                "match_type": "partial",
                "original_query": query,
                "match_quality": best_match[1]
            }

            # Add Contact type information if applicable
            if contact_type_match:
                from backend.infrastructure.pfc.python_api.types.contact import CONTACT_TYPES
                metadata["contact_type"] = contact_type_match
                metadata["all_contact_types"] = CONTACT_TYPES

            return [SearchResult(
                api_name=best_match[0],
                score=850,  # Lower than exact match (999) but indicates good match
                strategy=StrategyEnum.PATH,
                metadata=metadata
            )]

        return []

    def _build_contact_metadata(self, api_name: str) -> Optional[Dict[str, Any]]:
        """Build metadata for Contact type APIs.

        If the API name is a Contact type (BallBallContact, BallFacetContact, etc.),
        returns metadata with contact_type and all_contact_types information.
        Otherwise returns None.

        Args:
            api_name: API path like "BallBallContact.gap" or "Ball.vel"

        Returns:
            Metadata dict for Contact types, None for other types

        Example:
            >>> self._build_contact_metadata("BallBallContact.gap")
            {'contact_type': 'BallBallContact', 'all_contact_types': [...]}
            >>> self._build_contact_metadata("Ball.vel")
            None
        """
        from backend.infrastructure.pfc.python_api.types.contact import CONTACT_TYPES

        # Extract class name from API path
        # Handle both "BallBallContact.gap" and "itasca.BallBallContact.gap"
        parts = api_name.split('.')
        if len(parts) < 2:
            return None

        # Check second-to-last part (class name position)
        class_name = parts[-2]

        # If it's a Contact type, build metadata
        if class_name in CONTACT_TYPES:
            return {
                'contact_type': class_name,
                'all_contact_types': CONTACT_TYPES
            }

        return None

    def _calculate_attr_match_score(self, query_attr: str, api_attr: str) -> int:
        """Calculate match quality between query attribute and API attribute.

        Scoring rules:
        - Exact match: 100 (shouldn't happen, handled by earlier strategies)
        - One is prefix of the other (3+ chars): 80
        - One is substring of the other: 60
        - No match: 0

        Args:
            query_attr: Attribute name from query (lowercase)
            api_attr: Attribute name from API (lowercase)

        Returns:
            Match score (0-100)

        Example:
            >>> self._calculate_attr_match_score("velocity", "vel")
            80  # "vel" is prefix of "velocity"
            >>> self._calculate_attr_match_score("pos", "position")
            80  # "pos" is prefix of "position"
        """
        if query_attr == api_attr:
            return 100  # Exact match (shouldn't happen due to earlier strategies)

        # Prefix matching (minimum 3 chars to avoid false positives)
        min_prefix_len = 3
        if len(query_attr) >= min_prefix_len and len(api_attr) >= min_prefix_len:
            # Check if one is prefix of the other
            if query_attr.startswith(api_attr[:min_prefix_len]) or \
               api_attr.startswith(query_attr[:min_prefix_len]):
                return 80

        # Substring matching (one is contained in the other)
        if query_attr in api_attr or api_attr in query_attr:
            return 60

        return 0
