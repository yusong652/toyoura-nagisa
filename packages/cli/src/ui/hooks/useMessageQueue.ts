/**
 * Message Queue Hook
 * Reference: Gemini CLI ui/hooks/useMessageQueue.ts
 *
 * Manages message queuing during streaming responses.
 * Allows users to queue messages while the AI is responding
 * and automatically sends them when streaming completes.
 */

import { useCallback, useEffect, useState } from 'react';
import { StreamingState } from '../contexts/StreamingContext.js';

export interface UseMessageQueueOptions {
  isConnected: boolean;
  streamingState: StreamingState;
  submitQuery: (query: string) => void;
}

export interface UseMessageQueueReturn {
  messageQueue: string[];
  addMessage: (message: string) => void;
  clearQueue: () => void;
  getQueuedMessagesText: () => string;
  popAllMessages: (onPop: (messages: string | undefined) => void) => void;
}

/**
 * Hook for managing message queuing during streaming responses.
 */
export function useMessageQueue({
  isConnected,
  streamingState,
  submitQuery,
}: UseMessageQueueOptions): UseMessageQueueReturn {
  const [messageQueue, setMessageQueue] = useState<string[]>([]);

  // Add a message to the queue
  const addMessage = useCallback((message: string) => {
    const trimmedMessage = message.trim();
    if (trimmedMessage.length > 0) {
      setMessageQueue((prev) => [...prev, trimmedMessage]);
    }
  }, []);

  // Clear the entire queue
  const clearQueue = useCallback(() => {
    setMessageQueue([]);
  }, []);

  // Get all queued messages as a single text string
  const getQueuedMessagesText = useCallback(() => {
    if (messageQueue.length === 0) return '';
    return messageQueue.join('\n\n');
  }, [messageQueue]);

  // Pop all messages from the queue and return them as a single string
  const popAllMessages = useCallback(
    (onPop: (messages: string | undefined) => void) => {
      setMessageQueue((prev) => {
        if (prev.length === 0) {
          onPop(undefined);
          return prev;
        }
        const allMessages = prev.join('\n\n');
        onPop(allMessages);
        return [];
      });
    },
    [],
  );

  // Process queued messages when streaming becomes idle
  useEffect(() => {
    if (
      isConnected &&
      streamingState === StreamingState.Idle &&
      messageQueue.length > 0
    ) {
      const combinedMessage = messageQueue.join('\n\n');
      setMessageQueue([]);
      submitQuery(combinedMessage);
    }
  }, [isConnected, streamingState, messageQueue, submitQuery]);

  return {
    messageQueue,
    addMessage,
    clearQueue,
    getQueuedMessagesText,
    popAllMessages,
  };
}
