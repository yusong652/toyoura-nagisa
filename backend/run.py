import sys
import uvicorn
from pathlib import Path

# 使用 pathlib 优雅处理路径
_CURRENT_FILE = Path(__file__)
_BACKEND_DIR = _CURRENT_FILE.parent
_PROJECT_ROOT = _BACKEND_DIR.parent

# Add parent directory to path so that backend module can be found
sys.path.insert(0, str(_PROJECT_ROOT))

if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True) 