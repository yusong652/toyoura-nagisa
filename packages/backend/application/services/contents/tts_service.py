"""
TTS Service - Business logic for text-to-speech processing.

This service handles TTS synthesis with error handling, validation,
and data transformation for audio content.
"""
import base64
from typing import Optional, Dict, Any
from backend.infrastructure.tts.base import BaseTTS


class TTSService:
    """
    Service layer for TTS operations.

    Provides business logic for TTS synthesis including:
    - Audio generation and validation
    - Error handling and graceful degradation
    - Base64 encoding for transport
    """

    @staticmethod
    async def process_sentence(sentence: str, tts_engine: BaseTTS) -> Optional[Dict[str, Any]]:
        """
        Process TTS synthesis for a single sentence.

        This method orchestrates the complete TTS pipeline:
        1. Validates input and engine status
        2. Synthesizes audio via TTS engine
        3. Validates audio output
        4. Encodes for transport

        Args:
            sentence: Text to synthesize
            tts_engine: TTS engine implementation

        Returns:
            Optional[Dict[str, Any]]: Synthesis result or None
                - text: str - Original sentence
                - audio: Optional[str] - Base64 encoded audio or None
                - error: Optional[str] - Error message if synthesis failed

        Example:
            >>> tts_service = TTSService()
            >>> result = await tts_service.process_sentence("Hello world", engine)
            >>> if result and result['audio']:
            ...     print(f"Synthesized: {result['text']}")
        """
        # Validate input
        if sentence is None or sentence == '':
            return None

        # Handle whitespace-only sentences
        if sentence.strip() == '':
            return {'text': sentence, 'audio': None}

        try:
            # If TTS engine is disabled, return text only
            if not tts_engine.enabled:
                return {'text': sentence, 'audio': None}

            # Synthesize audio
            audio_bytes = await tts_engine.synthesize(sentence)

            # Validate audio data
            if not audio_bytes or len(audio_bytes) == 0:
                return {
                    'text': sentence,
                    'audio': None,
                    'error': 'Empty audio data from TTS engine'
                }

            # Validate if audio data is valid byte stream
            if not isinstance(audio_bytes, bytes):
                return {
                    'text': sentence,
                    'audio': None,
                    'error': f'Invalid audio data type: {type(audio_bytes)}'
                }

            # Encode audio for transport
            try:
                audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
                return {'text': sentence, 'audio': audio_b64}
            except Exception as b64_error:
                print(f"Base64 encoding failed: {b64_error}")
                return {
                    'text': sentence,
                    'audio': None,
                    'error': f'Base64 encoding failed: {str(b64_error)}'
                }

        except Exception as e:
            print(f"TTS synthesis failed: {e}")
            return {'text': sentence, 'audio': None, 'error': str(e)}
