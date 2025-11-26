/**
 * useSessionManagement Hook
 *
 * Manages session lifecycle: switching, creating, and history loading.
 * Extracted from AppContainer to follow gemini-cli's hook-driven architecture.
 */

import { useCallback } from 'react';
import { sessionService, type ConnectionManager, type SessionManager } from '@aiNagisa/core';
import { MessageType, type ContentBlock } from '../types.js';
import type { useHistoryManager } from './useHistoryManager.js';

interface UseSessionManagementParams {
  connectionManager: ConnectionManager;
  sessionManager: SessionManager;
  historyManager: ReturnType<typeof useHistoryManager>;
  clearQueue: () => void;
  setCurrentSessionId: (sessionId: string) => void;
}

interface UseSessionManagementReturn {
  switchSession: (sessionId: string) => Promise<void>;
  createSession: (name?: string) => Promise<string>;
}

/**
 * Convert backend history messages to CLI history items
 */
function convertBackendHistory(
  history: any[],
  historyManager: ReturnType<typeof useHistoryManager>
): void {
  for (const msg of history) {
    const timestamp = msg.timestamp ? new Date(msg.timestamp).getTime() : Date.now();

    if (msg.role === 'user') {
      // User message - extract text content
      let textContent = '';
      if (typeof msg.content === 'string') {
        textContent = msg.content;
      } else if (Array.isArray(msg.content)) {
        // Check for tool_result blocks (user messages can contain tool results)
        for (const block of msg.content) {
          if (block.type === 'text' && block.text) {
            textContent += block.text;
          } else if (block.type === 'tool_result') {
            // Add tool result as a separate history item
            const resultContent = block.content?.parts
              ?.map((p: any) => p.text || '')
              .join('\n') || '';
            historyManager.addItem({
              type: MessageType.TOOL_RESULT,
              toolCallId: block.tool_use_id || '',
              content: resultContent,
              isError: block.is_error || false,
            }, timestamp);
          }
        }
      }
      // Only add user message if there's text content
      if (textContent.trim()) {
        historyManager.addItem({
          type: MessageType.USER,
          text: textContent,
        }, timestamp);
      }
    } else if (msg.role === 'assistant') {
      // Assistant message - process all content blocks
      const contentBlocks: ContentBlock[] = [];
      const toolCalls: Array<{ id: string; name: string; input: Record<string, unknown> }> = [];

      if (typeof msg.content === 'string') {
        contentBlocks.push({ type: 'text', text: msg.content });
      } else if (Array.isArray(msg.content)) {
        for (const block of msg.content) {
          if (block.type === 'text' && block.text) {
            contentBlocks.push({ type: 'text', text: block.text });
          } else if (block.type === 'thinking' && block.thinking) {
            contentBlocks.push({ type: 'thinking', thinking: block.thinking });
          } else if (block.type === 'tool_use') {
            // Collect tool calls to add as separate items
            toolCalls.push({
              id: block.id || '',
              name: block.name || '',
              input: block.input || {},
            });
          }
        }
      }

      // Add assistant message if there's text/thinking content
      if (contentBlocks.length > 0) {
        historyManager.addItem({
          type: MessageType.ASSISTANT,
          content: contentBlocks,
        }, timestamp);
      }

      // Add tool call items
      for (const tc of toolCalls) {
        historyManager.addItem({
          type: MessageType.TOOL_CALL,
          toolCallId: tc.id,
          toolName: tc.name,
          toolInput: tc.input,
        }, timestamp);
      }
    }
  }
}

export function useSessionManagement({
  connectionManager,
  sessionManager,
  historyManager,
  clearQueue,
  setCurrentSessionId,
}: UseSessionManagementParams): UseSessionManagementReturn {

  const switchSession = useCallback(async (sessionId: string) => {
    connectionManager.disconnect();
    setCurrentSessionId(sessionId);
    historyManager.clearItems();
    clearQueue();

    // Load chat history for the session
    try {
      const historyResponse = await sessionService.getSessionHistory(sessionId);
      if (historyResponse.history && historyResponse.history.length > 0) {
        convertBackendHistory(historyResponse.history, historyManager);
      }
    } catch (err) {
      console.error('[useSessionManagement] Failed to load session history:', err);
    }

    await connectionManager.connectToSession(sessionId);
  }, [connectionManager, historyManager, clearQueue, setCurrentSessionId]);

  const createSession = useCallback(async (name?: string) => {
    const sessionId = await sessionManager.createSession(name);
    await switchSession(sessionId);
    return sessionId;
  }, [sessionManager, switchSession]);

  return {
    switchSession,
    createSession,
  };
}
