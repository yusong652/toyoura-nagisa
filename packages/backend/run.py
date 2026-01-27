import sys
import os
import uvicorn
from pathlib import Path
from dotenv import load_dotenv

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
_PACKAGES_DIR = _BACKEND_DIR.parent
_PROJECT_ROOT = _PACKAGES_DIR.parent

# Load .env from project root
load_dotenv(_PROJECT_ROOT / ".env")

# Add packages directory to path so that backend module can be found
sys.path.insert(0, str(_PACKAGES_DIR))

# Change working directory to project root for relative paths (chat/data, memory_db, etc.)
os.chdir(_PROJECT_ROOT)

if __name__ == "__main__":
    from backend.config import get_dev_config

    dev_config = get_dev_config()

    # Configure reload behavior
    reload_kwargs = {}
    if dev_config.enable_reload:
        # Use reload_dirs instead of reload_excludes for better compatibility
        # Only watch specific code directories to avoid scanning data directories
        reload_kwargs["reload_dirs"] = [
            str(_BACKEND_DIR / "application"),
            str(_BACKEND_DIR / "domain"),
            str(_BACKEND_DIR / "infrastructure"),
            str(_BACKEND_DIR / "presentation"),
            str(_BACKEND_DIR / "config"),
            str(_BACKEND_DIR / "shared"),
            str(_BACKEND_DIR / "app.py"),
        ]
        # Include .md files for prompt template changes
        reload_kwargs["reload_includes"] = ["*.py", "*.md"]

    uvicorn.run(
        "backend.app:app",
        host=dev_config.host,
        port=dev_config.port,
        reload=dev_config.enable_reload,
        timeout_graceful_shutdown=2,  # Fast shutdown for development
        **reload_kwargs,
    )
