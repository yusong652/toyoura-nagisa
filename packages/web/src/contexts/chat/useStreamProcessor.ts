import { useCallback, useMemo } from 'react'
import { StreamProcessor, StreamEventHandlers } from '@toyoura-nagisa/core'

interface UseStreamProcessorProps {
  handleTitleUpdate: (data: any) => void
  handleSessionRefresh: (data: any) => Promise<void>
  handleKeyword: (data: any) => void
  handleContentUpdate: (data: any, messageId: string) => Promise<void>
  sessionRefreshSessions: () => Promise<any>
}

interface UseStreamProcessorReturn {
  processStream: (response: Response, options: {
    userMessageId: string
    botMessageId: string
  }) => Promise<void>
}

/**
 * React hook wrapper for core StreamProcessor.
 *
 * Provides React-specific lifecycle management and event handler binding
 * while delegating core stream processing logic to @toyoura-nagisa/core.
 */
export const useStreamProcessor = ({
  handleTitleUpdate,
  handleSessionRefresh,
  handleKeyword,
  handleContentUpdate,
  sessionRefreshSessions
}: UseStreamProcessorProps): UseStreamProcessorReturn => {

  // Create event handlers object for core processor
  const handlers = useMemo<StreamEventHandlers>(() => ({
    onTitleUpdate: handleTitleUpdate,
    onSessionRefresh: handleSessionRefresh,
    onKeyword: handleKeyword,
    onContentUpdate: handleContentUpdate,
    onStreamComplete: sessionRefreshSessions
  }), [
    handleTitleUpdate,
    handleSessionRefresh,
    handleKeyword,
    handleContentUpdate,
    sessionRefreshSessions
  ])

  // Create core processor instance (recreate when handlers change)
  const processor = useMemo(() => new StreamProcessor(handlers), [handlers])

  /**
   * Process the entire SSE stream.
   *
   * Thin wrapper that delegates to core StreamProcessor.
   */
  const processStream = useCallback(async (
    response: Response,
    options: {
      userMessageId: string
      botMessageId: string
    }
  ) => {
    await processor.processStream(response, options)
  }, [processor])

  return {
    processStream
  }
}