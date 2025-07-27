"""Shared constants for coding tools.

Centralizes common patterns, limits, and configurations that are used across
multiple filesystem and coding tools to ensure consistency and reusability.
"""

from typing import Set

# -----------------------------------------------------------------------------
# File filtering constants
# -----------------------------------------------------------------------------

# Default exclusions for common large/irrelevant directories and patterns
# These are applied when use_default_excludes=True in various tools
DEFAULT_EXCLUDE_PATTERNS: Set[str] = {
    # Version control and IDE directories
    ".git",
    ".svn", 
    ".hg",
    ".idea",
    ".vscode",
    ".vs",
    
    # Build and distribution directories
    "node_modules",
    "dist",
    "build",
    "target",
    "bin",
    "obj",
    
    # Cache and temporary directories  
    "__pycache__",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    ".coverage",
    "coverage",
    ".nyc_output",
    
    # Environment and package directories
    "venv",
    ".venv", 
    "env",
    ".env",
    "virtualenv",
    "*.egg-info",
    
    # Framework-specific directories
    ".next",
    ".nuxt",
    ".angular",
    "bower_components",
    
    # OS-specific files and directories
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
    
    # Log and temporary files
    "*.log",
    "*.tmp",
    "*.temp",
    "*.swp",
    "*.swo",
    "*~",
}

# -----------------------------------------------------------------------------
# Performance and safety limits
# -----------------------------------------------------------------------------

# File operation limits
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MiB per file
MAX_TOTAL_SIZE_BYTES = 100 * 1024 * 1024  # 100 MiB total operation limit
MAX_FILE_SIZE_FOR_EDIT = 5 * 1024 * 1024  # 5 MiB max file size for editing operations

# Search operation limits  
MAX_FILES_DEFAULT = 1000  # Default maximum files to return
MAX_FILES_HARD_LIMIT = 5000  # Hard upper limit for safety
MAX_DIRECTORIES_DEFAULT = 500  # Default maximum directories to list

# Glob operation specific limits
GLOB_PATTERN_LIMIT = 50  # Maximum number of patterns in one glob operation
GLOB_RECENCY_THRESHOLD_HOURS = 24  # Files modified within this time are "recent"

# -----------------------------------------------------------------------------
# Text processing constants
# -----------------------------------------------------------------------------

TEXT_CHARSET_DEFAULT = "utf-8"
BINARY_DETECTION_SAMPLE_SIZE = 1024  # Bytes to sample for binary detection
INLINE_BINARY_MAX_BYTES = 512 * 1024  # 512 KiB for inline binary data

# -----------------------------------------------------------------------------
# Common file extensions
# -----------------------------------------------------------------------------

# Text file extensions (for content reading)
TEXT_EXTENSIONS = {
    ".txt", ".md", ".rst", ".asciidoc", ".org",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".vue", ".svelte",
    ".html", ".htm", ".xml", ".css", ".scss", ".sass", ".less",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx",
    ".java", ".kt", ".scala", ".groovy", ".clj", ".cljs",
    ".go", ".rs", ".swift", ".dart", ".lua", ".rb", ".php",
    ".sql", ".r", ".m", ".mm", ".pl", ".pm", ".hs", ".elm",
    ".dockerfile", ".makefile", ".cmake", ".gradle",
    ".tf", ".tfvars", ".hcl", ".nomad", ".consul",
}

# Binary file extensions (should not be read as text)
BINARY_EXTENSIONS = {
    # Archives and packages
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".deb", ".rpm", ".pkg", ".dmg", ".msi", ".exe",
    
    # Compiled code
    ".dll", ".so", ".dylib", ".a", ".lib", ".o", ".obj", 
    ".class", ".jar", ".war", ".ear", ".pyc", ".pyo",
    ".wasm", ".beam",
    
    # Media files
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
    ".mp3", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".mkv",
    ".wav", ".flac", ".ogg", ".aac", ".wma",
    
    # Documents
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".odt", ".ods", ".odp", ".rtf",
    
    # Data files
    ".db", ".sqlite", ".sqlite3", ".mdb", ".accdb",
    ".bin", ".dat", ".dump",
} 