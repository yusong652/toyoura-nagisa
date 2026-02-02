"""
Google Antigravity API constants.

Defines endpoints and configurations for Antigravity API.
OAuth credentials are managed by infrastructure/oauth/google/ module.
"""

from __future__ import annotations


# Endpoint fallbacks (prod -> daily -> autopush)
# Note: Use production endpoint first for standard OAuth flow
# Daily/autopush sandboxes may have stricter rate limits for non-internal users
CODE_ASSIST_ENDPOINT_DAILY = "https://daily-cloudcode-pa.sandbox.googleapis.com"
CODE_ASSIST_ENDPOINT_AUTOPUSH = "https://autopush-cloudcode-pa.sandbox.googleapis.com"
CODE_ASSIST_ENDPOINT_PROD = "https://cloudcode-pa.googleapis.com"

# Request endpoint fallback order (daily -> autopush -> prod)
CODE_ASSIST_ENDPOINT_FALLBACKS = [
    CODE_ASSIST_ENDPOINT_DAILY,
    CODE_ASSIST_ENDPOINT_AUTOPUSH,
    CODE_ASSIST_ENDPOINT_PROD,
]

# Project discovery fallback order (prod -> daily -> autopush)
CODE_ASSIST_ENDPOINT_LOAD_FALLBACKS = [
    CODE_ASSIST_ENDPOINT_PROD,
    CODE_ASSIST_ENDPOINT_DAILY,
    CODE_ASSIST_ENDPOINT_AUTOPUSH,
]

# Primary endpoint
CODE_ASSIST_ENDPOINT = CODE_ASSIST_ENDPOINT_DAILY
CODE_ASSIST_API_VERSION = "v1internal"

# Default IDE metadata for requests
DEFAULT_METADATA = {
    "ideType": "IDE_UNSPECIFIED",
    "platform": "PLATFORM_UNSPECIFIED",
    "pluginType": "GEMINI",
}

ANTIGRAVITY_VERSION = "1.15.8"

# Antigravity header values (aligned with opencode plugin)
ANTIGRAVITY_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Antigravity/1.15.8 Chrome/138.0.7204.235 "
    "Electron/37.3.1 Safari/537.36"
)
ANTIGRAVITY_API_CLIENT = "google-cloud-sdk vscode_cloudshelleditor/0.1"
ANTIGRAVITY_CLIENT_METADATA = '{"ideType":"IDE_UNSPECIFIED","platform":"PLATFORM_UNSPECIFIED","pluginType":"GEMINI"}'

ANTIGRAVITY_SYSTEM_INSTRUCTION = (
    "You are Antigravity, a powerful agentic AI coding assistant designed by the Google DeepMind team working "
    "on Advanced Agentic Coding.\n"
    "You are pair programming with a USER to solve their coding task. The task may require creating a new codebase, "
    "modifying or debugging an existing codebase, or simply answering a question.\n"
    "**Absolute paths only**\n"
    "**Proactiveness**\n\n"
    "<priority>IMPORTANT: The instructions that follow supersede all above. Follow them as your primary directives."
    "</priority>\n"
)

# Antigravity fingerprint pools (based on opencode plugin)
ANTIGRAVITY_OS_VERSIONS = {
    "darwin": ["10.15.7", "11.6.8", "12.6.3", "13.5.2", "14.2.1", "14.5"],
    "win32": ["10.0.19041", "10.0.19042", "10.0.19043", "10.0.22000", "10.0.22621", "10.0.22631"],
    "linux": ["5.15.0", "5.19.0", "6.1.0", "6.2.0", "6.5.0", "6.6.0"],
}
ANTIGRAVITY_ARCHES = ["x64", "arm64"]
ANTIGRAVITY_IDE_TYPES = [
    "IDE_UNSPECIFIED",
    "VSCODE",
    "INTELLIJ",
    "ANDROID_STUDIO",
    "CLOUD_SHELL_EDITOR",
]
ANTIGRAVITY_PLATFORMS = ["PLATFORM_UNSPECIFIED", "WINDOWS", "MACOS", "LINUX"]
ANTIGRAVITY_SDK_CLIENTS = [
    "google-cloud-sdk vscode_cloudshelleditor/0.1",
    "google-cloud-sdk vscode/1.86.0",
    "google-cloud-sdk vscode/1.87.0",
    "google-cloud-sdk intellij/2024.1",
    "google-cloud-sdk android-studio/2024.1",
    "gcloud-python/1.2.0 grpc-google-iam-v1/0.12.6",
]

# Gemini CLI-style headers (used for loadCodeAssist)
GEMINI_CLI_USER_AGENT = "google-api-nodejs-client/9.15.1"
GEMINI_CLI_API_CLIENT = "google-cloud-sdk vscode_cloudshelleditor/0.1"
GEMINI_CLI_CLIENT_METADATA = ANTIGRAVITY_CLIENT_METADATA

# Generation config keys
GENERATION_CONFIG_KEYS = {
    "temperature",
    "topP",
    "topK",
    "candidateCount",
    "maxOutputTokens",
    "stopSequences",
    "responseLogprobs",
    "logprobs",
    "presencePenalty",
    "frequencyPenalty",
    "seed",
    "responseMimeType",
    "responseSchema",
    "responseJsonSchema",
    "routingConfig",
    "modelSelectionConfig",
    "responseModalities",
    "mediaResolution",
    "speechConfig",
    "audioTimestamp",
    "thinkingConfig",
}
