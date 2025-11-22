"""Search strategies for PFC SDK documentation.

This package previously provided pluggable search strategies.
Now all search is handled by the unified BM25 engine:
- backend.infrastructure.pfc.shared.query.APISearch (BM25-based search)

The BM25 engine handles both natural language and API path queries
through smart tokenization and name boosting.
"""

__all__ = []
