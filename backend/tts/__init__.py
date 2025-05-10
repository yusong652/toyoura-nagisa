"""
TTS module for aiNagisa
"""

from .base import BaseTTS, TTSConfig, TTSException, TTSSynthesisError, TTSInitError
from .remote.fish_audio import FishAudioTTS
