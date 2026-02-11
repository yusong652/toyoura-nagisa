"""
Unified workspace resolution for toyoura-nagisa.

This module provides a single source of truth for determining workspace directories
based on agent profiles. Both system prompt construction and tool execution use
the same logic to ensure consistency.

Design principle: agent_profile is always passed explicitly as a parameter,
never retrieved implicitly from context_manager state.
"""

import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Cache workspace result to avoid frequent queries
# Key: agent_profile, Value: (timestamp, Path)
_workspace_cache: dict[str, tuple[float, Path]] = {}
WORKSPACE_CACHE_TTL = 300.0  # 5 minutes


async def get_workspace_for_profile(agent_profile: str, session_id: Optional[str] = None) -> Path:
    """
    Determine workspace directory based on agent profile.

    This is the SINGLE SOURCE OF TRUTH for workspace resolution.
    All components (system prompts, coding tools, etc.) must use this function.

    Workspace Strategy:
        - Configured PFC workspace (PFC_WORKSPACE in config/pfc.py)
        - Local pfc_workspace fallback (toyoura-nagisa/pfc_workspace)

    Args:
        agent_profile: Agent profile type ("pfc_expert", "disabled", etc.)
        session_id: Optional session ID (reserved for future use, currently unused)

    Returns:
        Path object for the workspace directory

    Note:
        session_id is currently reserved for future use (workspace isolation).
    """
    # Check memory cache first
    current_time = time.time()
    if agent_profile in _workspace_cache:
        timestamp, cached_path = _workspace_cache[agent_profile]
        if current_time - timestamp < WORKSPACE_CACHE_TTL:
            return cached_path

    # Workspace resolution: use configured PFC workspace path

    # Primary: Use configured PFC workspace if available
    try:
        from backend.config.pfc import get_pfc_workspace

        configured_workspace = get_pfc_workspace()
        if configured_workspace:
            if agent_profile.startswith("pfc"): # Only log for PFC profiles to avoid noise
                logger.info(f"✓ Using configured PFC workspace: {configured_workspace}")
            
            # Cache the fallback result too
            _workspace_cache[agent_profile] = (current_time, configured_workspace)
            return configured_workspace
    except ImportError:
        logger.debug("PFC config not available, skipping configured workspace check")
    except Exception as e:
        logger.warning(f"Failed to get configured PFC workspace: {e}")

    # Fallback: Local pfc_workspace (development/testing)
    try:
        from backend.shared.utils.prompt.config import BASE_DIR

        pfc_workspace = BASE_DIR / "pfc_workspace"
        pfc_workspace.mkdir(parents=True, exist_ok=True)
        # logger.info(f"✓ Using fallback PFC workspace: {pfc_workspace}") # Too noisy
        
        _workspace_cache[agent_profile] = (current_time, pfc_workspace)
        return pfc_workspace
    except Exception as e:
        logger.warning(f"Failed to determine fallback PFC workspace: {e}")
        fallback = Path.cwd() / "pfc_workspace"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
