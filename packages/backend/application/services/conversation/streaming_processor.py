"""
Streaming Processor - Handles LLM streaming response processing.

Extracts streaming-related logic from ChatOrchestrator for better separation of concerns.
"""
from typing import Any, Optional, AsyncGenerator
from backend.domain.models.streaming import StreamingChunk
from backend.application.services.conversation.models import StreamingState


class StreamingProcessor:
    """
    Processes LLM streaming responses and manages streaming state.

    Responsibilities:
    - Stream chunk processing and accumulation
    - User interrupt detection during streaming
    - Content block construction for WebSocket updates
    - Response construction from accumulated chunks
    """

    def __init__(self, llm_client, session_id: str):
        """
        Initialize StreamingProcessor.

        Args:
            llm_client: LLM client for response processing
            session_id: Session identifier for interrupt checking
        """
        self.llm_client = llm_client
        self.session_id = session_id
        self._processor = llm_client._get_response_processor()

    async def process_stream(
        self,
        stream: AsyncGenerator[StreamingChunk, None],
        state: StreamingState
    ) -> tuple[bool, Any]:
        """
        Process streaming response from LLM.

        Args:
            stream: Async generator of StreamingChunk
            state: StreamingState to accumulate chunks

        Returns:
            tuple[bool, Any]: (was_interrupted, constructed_response)
        """
        from backend.infrastructure.monitoring import get_status_monitor
        from backend.infrastructure.websocket.notification_service import WebSocketNotificationService

        async for chunk in stream:
            # Check for user interrupt
            status_monitor = get_status_monitor(self.session_id)
            if status_monitor.is_user_interrupted():
                return (True, self._construct_response(state))

            # Accumulate chunk
            state.add_chunk(chunk)

            # Send content update via WebSocket
            content_blocks = state.get_content_blocks()
            if content_blocks:
                await WebSocketNotificationService.send_streaming_update(
                    session_id=self.session_id,
                    message_id=state.message_id,
                    content=content_blocks,
                    streaming=True
                )

        # Ensure at least one update was sent
        if not state.text_buffer and not state.thinking_buffer:
            await WebSocketNotificationService.send_streaming_update(
                session_id=self.session_id,
                message_id=state.message_id,
                content=[{"type": "text", "text": ""}],
                streaming=True
            )

        return (False, self._construct_response(state))

    def _construct_response(self, state: StreamingState) -> Any:
        """Construct response from accumulated chunks."""
        return self._processor.construct_response_from_chunks(state.collected_chunks)

    def has_tool_calls(self, response: Any) -> bool:
        """Check if response contains tool calls."""
        return self._processor.has_tool_calls(response)

    def extract_tool_calls(self, response: Any) -> list:
        """Extract tool calls from response."""
        return self._processor.extract_tool_calls(response)

    def format_for_storage(self, response: Any, tool_calls: Optional[list] = None) -> Any:
        """Format response for storage."""
        if tool_calls:
            return self._processor.format_response_for_storage(response, tool_calls)
        return self._processor.format_response_for_storage(response)

    def extract_usage(self, state: StreamingState) -> Optional[dict]:
        """Extract token usage from streaming state."""
        if not state.collected_chunks:
            return None

        last_chunk = state.collected_chunks[-1]
        if not last_chunk.metadata or 'prompt_token_count' not in last_chunk.metadata:
            return None

        from backend.shared.constants.model_limits import DEFAULT_MAX_TOKENS

        prompt_tokens = last_chunk.metadata.get('prompt_token_count', 0)
        completion_tokens = last_chunk.metadata.get('candidates_token_count', 0)
        total_tokens = last_chunk.metadata.get('total_token_count', 0)

        return {
            'prompt_tokens': prompt_tokens or 0,
            'completion_tokens': completion_tokens or 0,
            'total_tokens': total_tokens or 0,
            'tokens_left': max(0, DEFAULT_MAX_TOKENS - (prompt_tokens or 0))
        }
