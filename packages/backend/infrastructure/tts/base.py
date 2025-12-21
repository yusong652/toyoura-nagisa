from abc import ABC, abstractmethod
from typing import Optional, Union, Dict, Any
from pathlib import Path
from pydantic import BaseModel
from backend.infrastructure.tts.utils import clean_text_for_tts
from datetime import datetime

class TTSRequest(BaseModel):
    text: str

class TTSException(Exception):
    """Base exception class for TTS module"""
    pass

class TTSInitError(TTSException):
    """TTS initialization error"""
    pass

class TTSSynthesisError(TTSException):
    """TTS synthesis error"""
    pass

class TTSConfig:
    """TTS configuration base class.

    Used for storing and managing TTS engine configuration parameters.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize configuration.

        Args:
            config: Configuration dictionary, optional
        """
        self._config = config or {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            key: Configuration key
            default: Default value

        Returns:
            Configuration value, or default if not found
        """
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config[key] = value

class BaseTTS(ABC):
    """Abstract base class for TTS engines.

    Defines the basic interface that all TTS engines must implement.
    """

    def __init__(self, config: TTSConfig):
        """Initialize TTS engine.

        Args:
            config: TTS configuration object
        """
        self.config = config
        self._is_ready = False
        self._enabled = False  # Disabled by default (CLI has no TTS toggle, will be separated later)

    @property
    def enabled(self) -> bool:
        """Get TTS engine enabled status."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Set TTS engine enabled status."""
        self._enabled = value

    def clean_text(self, text: str) -> str:
        """Clean kaomoji and special symbols from text.

        Args:
            text: Original text

        Returns:
            str: Cleaned text
        """
        return clean_text_for_tts(text)
    
    def save_audio_to_file(self, audio_bytes: bytes, output_path: Optional[Union[str, Path]] = None, audio_format: str = "mp3") -> Optional[str]:
        """Save audio bytes to file, supporting multiple audio formats.

        Args:
            audio_bytes: Audio bytes to save
            output_path: Output file path, optional. Auto-generates filename if not provided
            audio_format: Audio format (e.g., 'mp3', 'wav'), defaults to 'mp3'

        Returns:
            Optional[str]: Saved file path, or None if save failed
        """
        try:
            if not output_path:
                output_dir = Path(__file__).parent / "data" / "tts_outputs"
                output_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                output_path = output_dir / f"tts_{timestamp}.{audio_format}"
            else:
                output_path = Path(output_path)
                if not output_path.suffix:
                    output_path = output_path.with_suffix(f".{audio_format}")
                output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'wb') as f:
                f.write(audio_bytes)
            return str(output_path.absolute())
        except Exception as e:
            print(f"Error saving audio to file: {e}")
            return None
    
    @property
    def is_ready(self) -> bool:
        """Check if TTS engine is ready.

        Returns:
            bool: Whether the engine is ready
        """
        return self._is_ready

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize TTS engine.

        Returns:
            bool: Whether initialization was successful

        Raises:
            TTSInitError: Raised when initialization fails
        """
        pass

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        output_path: Optional[Union[str, Path]] = None,
        reference_id: Optional[int] = None,
        language: Optional[str] = None,
        speed: float = 1.0,
        **kwargs
    ) -> Union[bytes, str]:
        """Convert text to speech.

        Args:
            text: Text to convert
            output_path: Output audio file path, optional
            reference_id: Speaker ID, optional
            language: Language code, optional
            speed: Speech rate, defaults to 1.0
            **kwargs: Additional parameters

        Returns:
            Union[bytes, str]:
                - If output_path is provided, returns the saved file path
                - If output_path is not provided, returns audio data as bytes

        Raises:
            TTSSynthesisError: Raised when synthesis error occurs
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown TTS engine.

        Release resources and clean up state.
        """
        pass
