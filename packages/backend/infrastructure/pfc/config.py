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

# Command documentation root (version-controlled, JSON format)
# Contains PFC command documentation with 115 commands across 7 categories
PFC_COMMAND_DOCS_ROOT = _CURRENT_DIR / "resources" / "command_docs"

# Reference documentation (version-controlled, JSON format)
# Syntax elements used within commands: contact models, range elements, etc.
PFC_REFERENCES_ROOT = _CURRENT_DIR / "resources" / "references"

# Contact models subdirectory (within references)
PFC_CONTACT_MODELS_ROOT = PFC_REFERENCES_ROOT / "contact-models"

# Runtime semantic index (generated dynamically, NOT version-controlled)
# Future: Will contain ChromaDB/FAISS embeddings for semantic search
PFC_DOCS_INDEX = _PROJECT_ROOT / "data" / "pfc" / "python_sdk_index"

# ============================================================================
# SDK Query Configuration
# ============================================================================

# Maximum number of API matches to return from keyword search
# - Top 1 result gets full documentation
# - Remaining results show brief signatures only
SDK_SEARCH_TOP_N = 3

# ============================================================================
# Future: Semantic Search Configuration
# ============================================================================

# When implementing semantic search, uncomment and configure:
# PFC_EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI model
# PFC_EMBEDDING_DIMENSIONS = 1536
# PFC_INDEX_TYPE = "chromadb"  # or "faiss", "qdrant"
