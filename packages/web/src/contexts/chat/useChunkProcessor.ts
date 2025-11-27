import { useCallback, useMemo } from 'react'
import { ChunkProcessor, ChunkEventHandlers, ChunkData as CoreChunkData } from '@aiNagisa/core'
import { useWebSocketTTS } from './useWebSocketTTS'

// Re-export ChunkData from core for backward compatibility
export type ChunkData = CoreChunkData

interface UseChunkProcessorProps {
  ttsEnabled: boolean
  processAudioData: (audioData: string, count: number) => Promise<boolean>
  updateMessageText: (messageId: string, text: string, options?: any) => void
  finalizeMessage: (messageId: string) => void
}

interface UseChunkProcessorReturn {
  processChunk: (chunk: CoreChunkData, messageId: string) => Promise<void>
  resetProcessor: () => void
  setupTTSHandler?: (messageId: string) => void
  cleanupTTSHandler?: () => void
  updateTTSMessageId?: (oldId: string, newId: string) => void
}

/**
 * React hook wrapper for core ChunkProcessor.
 *
 * Provides React-specific lifecycle management and event handler binding
 * while delegating core chunk processing logic to @aiNagisa/core.
 *
 * Also integrates WebSocket TTS functionality for real-time audio streaming.
 */
export const useChunkProcessor = ({
  ttsEnabled,
  processAudioData,
  updateMessageText,
  finalizeMessage
}: UseChunkProcessorProps): UseChunkProcessorReturn => {

  // WebSocket TTS processor - handles real-time TTS via WebSocket events
  const webSocketTTS = useWebSocketTTS({
    ttsEnabled,
    processAudioData,
    updateMessageText,
    finalizeMessage
  })

  // Create event handlers object for core processor
  const handlers = useMemo<ChunkEventHandlers>(() => ({
    onTextUpdate: updateMessageText,
    onAudioChunk: processAudioData,
    onMessageFinalize: finalizeMessage
  }), [updateMessageText, processAudioData, finalizeMessage])

  // Create core processor instance (recreate when handlers or ttsEnabled change)
  const processor = useMemo(
    () => new ChunkProcessor(handlers, ttsEnabled),
    [handlers, ttsEnabled]
  )

  /**
   * Main chunk processing entry point.
   *
   * Thin wrapper that delegates to core ChunkProcessor.
   */
  const processChunk = useCallback(async (
    chunk: CoreChunkData,
    messageId: string
  ): Promise<void> => {
    await processor.processChunk(chunk, messageId)
  }, [processor])

  /**
   * Reset processor state for new stream.
   */
  const resetProcessor = useCallback(() => {
    processor.reset()
  }, [processor])

  return {
    processChunk,
    resetProcessor,
    setupTTSHandler: webSocketTTS.setupTTSHandler,
    cleanupTTSHandler: webSocketTTS.cleanupTTSHandler,
    updateTTSMessageId: webSocketTTS.updateMessageId
  }
}