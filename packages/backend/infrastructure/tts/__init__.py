"""
TTS module for toyoura-nagisa
"""

from backend.infrastructure.tts.base import BaseTTS, TTSConfig, TTSException, TTSSynthesisError, TTSInitError
from backend.infrastructure.tts.remote.fish_audio import FishAudioTTS
