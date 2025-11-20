import sys
import os
import uvicorn
from pathlib import Path

# Set UTF-8 encoding for Windows
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    import codecs
    import locale
    # Force UTF-8 encoding on Windows
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

_CURRENT_FILE = Path(__file__)
_BACKEND_DIR = _CURRENT_FILE.parent
_PROJECT_ROOT = _BACKEND_DIR.parent

# Add parent directory to path so that backend module can be found
sys.path.insert(0, str(_PROJECT_ROOT))

if __name__ == "__main__":
    from backend.config import get_dev_config

    dev_config = get_dev_config()

    # Configure reload behavior
    reload_kwargs = {}
    if dev_config.enable_reload:
        # Option 1: Exclude data directories (recommended for flexibility)
        # This allows monitoring all code while excluding data/cache directories
        reload_kwargs["reload_excludes"] = [
            "**/workspace/**",          # User workspace files
            "**/pfc_workspace/**",      # PFC workspace files
            "**/memory_db/**",          # ChromaDB vector database
            "**/chat/data/**",          # Session data
            "**/__pycache__/**",        # Python cache
            "**/*.pyc",                 # Compiled Python files
            "**/.pytest_cache/**",      # Pytest cache
            "**/.git/**",               # Git directory
            "**/node_modules/**",       # Node modules (if any)
            "**/*.log",                 # Log files
            "**/.DS_Store",             # macOS metadata
        ]

        # Option 2: Only watch specific directories (more restrictive, commented out)
        # Uncomment this and comment out reload_excludes above for stricter control
        # reload_kwargs["reload_dirs"] = [
        #     str(_BACKEND_DIR / "application"),
        #     str(_BACKEND_DIR / "domain"),
        #     str(_BACKEND_DIR / "infrastructure"),
        #     str(_BACKEND_DIR / "presentation"),
        #     str(_BACKEND_DIR / "config"),
        #     str(_BACKEND_DIR / "shared"),
        #     str(_BACKEND_DIR / "app.py"),
        # ]

    uvicorn.run(
        "backend.app:app",
        host=dev_config.host,
        port=dev_config.port,
        reload=dev_config.enable_reload,
        **reload_kwargs
    ) 