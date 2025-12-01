/**
 * useSessionManagement Hook
 *
 * Manages session lifecycle: switching, creating, and history loading.
 * Extracted from AppContainer to follow gemini-cli's hook-driven architecture.
 */

import { useCallback } from 'react';
import { sessionService, type ConnectionManager, type SessionManager } from '@toyoura-nagisa/core';
import { MessageType, type ContentBlock } from '../types.js';
import type { useHistoryManager } from './useHistoryManager.js';

interface UseSessionManagementParams {
  connectionManager: ConnectionManager;
  sessionManager: SessionManager;
  historyManager: ReturnType<typeof useHistoryManager>;
  setCurrentSessionId: (sessionId: string) => void;
}

interface UseSessionManagementReturn {
  switchSession: (sessionId: string) => Promise<void>;
  createSession: (name?: string) => Promise<string>;
  loadHistory: (sessionId: string) => Promise<void>;
}

/**
 * Pending tool pair for history conversion
 * Matches tool_call with its result for proper ordering
 */
interface HistoryToolPair {
  toolCallId: string;
  toolCall: {
    type: typeof MessageType.TOOL_CALL;
    toolCallId: string;
    toolName: string;
    toolInput: Record<string, unknown>;
  };
  toolResult: {
    type: typeof MessageType.TOOL_RESULT;
    toolCallId: string;
    toolName: string;
    content: string;
    isError: boolean;
    diff?: any;
  } | null;
  timestamp: number;
}

/**
 * Convert backend history messages to CLI history items
 * Uses pair matching to ensure tool_call and tool_result are adjacent
 */
function convertBackendHistory(
  history: any[],
  historyManager: ReturnType<typeof useHistoryManager>
): void {
  // Collect tool pairs for proper ordering
  const toolPairs: HistoryToolPair[] = [];

  for (const msg of history) {
    const timestamp = msg.timestamp ? new Date(msg.timestamp).getTime() : Date.now();

    if (msg.role === 'user') {
      // User message - extract text content and tool results
      let textContent = '';
      if (typeof msg.content === 'string') {
        textContent = msg.content;
      } else if (Array.isArray(msg.content)) {
        for (const block of msg.content) {
          if (block.type === 'text' && block.text) {
            textContent += block.text;
          } else if (block.type === 'tool_result') {
            // Find matching tool pair and fill result
            const pair = toolPairs.find((p) => p.toolCallId === block.tool_use_id);
            if (pair && !pair.toolResult) {
              const resultContent = block.content?.parts
                ?.map((p: any) => p.text || '')
                .join('\n') || '';
              pair.toolResult = {
                type: MessageType.TOOL_RESULT,
                toolCallId: block.tool_use_id || '',
                toolName: block.tool_name || '',
                content: resultContent,
                isError: block.is_error || false,
                diff: block.data?.diff,
              };
            }
          }
        }
      }
      // Only add user message if there's text content
      if (textContent.trim()) {
        // First, flush any pending tool pairs before user message
        for (const pair of toolPairs) {
          historyManager.addItem(pair.toolCall, pair.timestamp);
          if (pair.toolResult) {
            historyManager.addItem(pair.toolResult, pair.timestamp);
          }
        }
        toolPairs.length = 0;

        historyManager.addItem({
          type: MessageType.USER,
          text: textContent,
        }, timestamp);
      }
    } else if (msg.role === 'assistant') {
      // Assistant message - process all content blocks
      const contentBlocks: ContentBlock[] = [];
      let hasToolUse = false;

      if (typeof msg.content === 'string') {
        contentBlocks.push({ type: 'text', text: msg.content });
      } else if (Array.isArray(msg.content)) {
        for (const block of msg.content) {
          if (block.type === 'text' && block.text) {
            contentBlocks.push({ type: 'text', text: block.text });
          } else if (block.type === 'thinking' && block.thinking) {
            contentBlocks.push({ type: 'thinking', thinking: block.thinking });
          } else if (block.type === 'tool_use') {
            hasToolUse = true;
            // Create tool pair with result=null (placeholder)
            toolPairs.push({
              toolCallId: block.id || '',
              toolCall: {
                type: MessageType.TOOL_CALL,
                toolCallId: block.id || '',
                toolName: block.name || '',
                toolInput: block.input || {},
              },
              toolResult: null,
              timestamp,
            });
          }
        }
      }

      // Add assistant message if there's text/thinking content OR tool_use
      // (tool_use-only messages need the ⏺ prefix for visual consistency with streaming)
      if (contentBlocks.length > 0 || hasToolUse) {
        historyManager.addItem({
          type: MessageType.ASSISTANT,
          content: contentBlocks,
        }, timestamp);
      }
    }
  }

  // Flush remaining tool pairs at the end
  for (const pair of toolPairs) {
    historyManager.addItem(pair.toolCall, pair.timestamp);
    if (pair.toolResult) {
      historyManager.addItem(pair.toolResult, pair.timestamp);
    }
  }
}

export function useSessionManagement({
  connectionManager,
  sessionManager,
  historyManager,
  setCurrentSessionId,
}: UseSessionManagementParams): UseSessionManagementReturn {

  // Load history for a session (reusable, doesn't manage connection)
  const loadHistory = useCallback(async (sessionId: string) => {
    try {
      const historyResponse = await sessionService.getSessionHistory(sessionId);
      if (historyResponse.history && historyResponse.history.length > 0) {
        convertBackendHistory(historyResponse.history, historyManager);
      }
    } catch (err) {
      console.error('[useSessionManagement] Failed to load session history:', err);
    }
  }, [historyManager]);

  const switchSession = useCallback(async (sessionId: string) => {
    connectionManager.disconnect();
    setCurrentSessionId(sessionId);
    historyManager.clearItems();

    // Persist current session ID to storage (for CLI restart)
    await sessionManager.switchSession(sessionId);

    // Load chat history for the session
    await loadHistory(sessionId);

    await connectionManager.connectToSession(sessionId);
  }, [connectionManager, sessionManager, historyManager, setCurrentSessionId, loadHistory]);

  const createSession = useCallback(async (name?: string) => {
    const sessionId = await sessionManager.createSession(name);
    await switchSession(sessionId);
    return sessionId;
  }, [sessionManager, switchSession]);

  return {
    switchSession,
    createSession,
    loadHistory,
  };
}
