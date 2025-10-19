"""PFC (Particle Flow Code) Integration Configuration.

This module defines paths and settings for PFC integration, including:
- Static documentation sources (version-controlled)
- Runtime indexes for semantic search (generated dynamically)
"""

from pathlib import Path

# Base paths
_CURRENT_DIR = Path(__file__).parent
_BACKEND_DIR = _CURRENT_DIR.parent.parent
_PROJECT_ROOT = _BACKEND_DIR.parent

# ============================================================================
# Documentation Paths
# ============================================================================

# Static source documentation (version-controlled, JSON format)
# Contains PFC Python SDK API documentation exported from official docs
PFC_DOCS_SOURCE = _CURRENT_DIR / "resources" / "python_sdk_docs"

# Runtime semantic index (generated dynamically, NOT version-controlled)
# Future: Will contain ChromaDB/FAISS embeddings for semantic search
PFC_DOCS_INDEX = _PROJECT_ROOT / "data" / "pfc" / "python_sdk_index"

# ============================================================================
# Future: Semantic Search Configuration
# ============================================================================

# When implementing semantic search, uncomment and configure:
# PFC_EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI model
# PFC_EMBEDDING_DIMENSIONS = 1536
# PFC_INDEX_TYPE = "chromadb"  # or "faiss", "qdrant"
