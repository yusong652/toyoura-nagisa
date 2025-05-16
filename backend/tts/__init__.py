"""
TTS module for aiNagisa
"""

from backend.tts.base import BaseTTS, TTSConfig, TTSException, TTSSynthesisError, TTSInitError
from backend.tts.remote.fish_audio import FishAudioTTS
