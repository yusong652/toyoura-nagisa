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
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True) 