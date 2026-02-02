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

# Production-first fallback order for toyoura-nagisa
CODE_ASSIST_ENDPOINT_FALLBACKS = [
    CODE_ASSIST_ENDPOINT_PROD,
    CODE_ASSIST_ENDPOINT_DAILY,
    CODE_ASSIST_ENDPOINT_AUTOPUSH,
]

# Primary endpoint
CODE_ASSIST_ENDPOINT = CODE_ASSIST_ENDPOINT_PROD
CODE_ASSIST_API_VERSION = "v1internal"

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
