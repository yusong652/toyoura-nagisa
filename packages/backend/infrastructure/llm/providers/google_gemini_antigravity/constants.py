"""
Google Antigravity API constants.

Defines endpoints, OAuth credentials, and configurations for Antigravity API.
"""

from __future__ import annotations

import platform
import sys


# OAuth credentials (from antigravity/Gemini CLI)
ANTIGRAVITY_CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
ANTIGRAVITY_CLIENT_SECRET = "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"
ANTIGRAVITY_CALLBACK_PORT = 36742
ANTIGRAVITY_REDIRECT_URI = f"http://localhost:{ANTIGRAVITY_CALLBACK_PORT}/oauth-callback"

# OAuth scopes
ANTIGRAVITY_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
]


def _get_antigravity_platform() -> str:
    """Map Python platform to Antigravity's expected format."""
    platform_map = {
        "darwin": "darwin",
        "linux": "linux",
        "win32": "windows",
    }
    arch_map = {
        "arm64": "arm64",
        "aarch64": "arm64",
        "x86_64": "amd64",
        "amd64": "amd64",
        "i386": "386",
        "i686": "386",
    }
    p = platform_map.get(sys.platform, "linux")
    machine = platform.machine().lower()
    a = arch_map.get(machine, "amd64")
    return f"{p}/{a}"


ANTIGRAVITY_USER_AGENT = f"antigravity/1.15.8 {_get_antigravity_platform()}"
ANTIGRAVITY_API_CLIENT = "google-cloud-sdk vscode_cloudshelleditor/0.1"
ANTIGRAVITY_CLIENT_METADATA = '{"ideType":"IDE_UNSPECIFIED","platform":"PLATFORM_UNSPECIFIED","pluginType":"GEMINI"}'

# Endpoint fallbacks (prod -> daily -> autopush)
# Note: Use production endpoint first for standard OAuth flow
# Daily/autopush sandboxes may have stricter rate limits for non-internal users
CODE_ASSIST_ENDPOINT_DAILY = "https://daily-cloudcode-pa.sandbox.googleapis.com"
CODE_ASSIST_ENDPOINT_AUTOPUSH = "https://autopush-cloudcode-pa.sandbox.googleapis.com"
CODE_ASSIST_ENDPOINT_PROD = "https://cloudcode-pa.googleapis.com"

# Production-first fallback order for toyoura-nagisa
CODE_ASSIST_ENDPOINT_FALLBACKS = [
    CODE_ASSIST_ENDPOINT_PROD,
    CODE_ASSIST_ENDPOINT_DAILY,
    CODE_ASSIST_ENDPOINT_AUTOPUSH,
]

# Primary endpoint
CODE_ASSIST_ENDPOINT = CODE_ASSIST_ENDPOINT_PROD
CODE_ASSIST_API_VERSION = "v1internal"

# Default request headers for Antigravity
CODE_ASSIST_HEADERS = {
    "User-Agent": ANTIGRAVITY_USER_AGENT,
    "X-Goog-Api-Client": ANTIGRAVITY_API_CLIENT,
    "Client-Metadata": ANTIGRAVITY_CLIENT_METADATA,
}

# Default IDE metadata for requests
DEFAULT_METADATA = {
    "ideType": "IDE_UNSPECIFIED",
    "platform": "PLATFORM_UNSPECIFIED",
    "pluginType": "GEMINI",
}

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
