/**
 * Tool Confirmation Hook
 * Manages tool confirmation state and responses.
 *
 * Handles different confirmation types:
 * - edit: File modifications with diff display
 * - exec: Command execution (bash, shell)
 * - info: Generic tool confirmation
 *
 * Confirmation outcomes:
 * - approve: Execute the tool
 * - reject: Stop execution, user wants to provide input via main input
 * - reject_and_tell: Continue execution with user's brief instruction
 */

import { useState, useCallback } from 'react';
import type { ConnectionManager } from '@toyoura-nagisa/core';
import type { ToolConfirmationData } from '../types.js';
import type { ToolConfirmationEvent } from '../types/streamEvents.js';
import type { ConfirmationOutcome } from '../components/ToolConfirmationPrompt.js';

export interface UseToolConfirmationOptions {
  connectionManager: ConnectionManager;
  onConfirmationStart?: () => void;
  onConfirmationEnd?: (outcome: ConfirmationOutcome) => void;
}

export interface UseToolConfirmationReturn {
  pendingConfirmation: ToolConfirmationData | null;
  handleToolConfirmationRequest: (event: ToolConfirmationEvent) => void;
  confirmTool: (outcome: ConfirmationOutcome, message?: string) => void;
  clearConfirmation: () => void;
}

/**
 * Hook for managing tool confirmation flow.
 */
export function useToolConfirmation({
  connectionManager,
  onConfirmationStart,
  onConfirmationEnd,
}: UseToolConfirmationOptions): UseToolConfirmationReturn {
  const [pendingConfirmation, setPendingConfirmation] = useState<ToolConfirmationData | null>(null);

  // Handle tool confirmation request from backend
  const handleToolConfirmationRequest = useCallback(
    (event: ToolConfirmationEvent) => {
      const confirmationType = event.confirmation_type || 'info';

      let confirmationData: ToolConfirmationData;

      if (confirmationType === 'edit' && event.file_diff) {
        // Edit confirmation with diff display
        confirmationData = {
          type: 'edit',
          tool_call_id: event.tool_call_id,
          tool_name: event.tool_name,
          tool_input: {
            command: event.command,
            description: event.description,
          },
          description: event.description,
          fileName: event.file_name || 'unknown',
          filePath: event.file_path || '',
          fileDiff: event.file_diff,
          originalContent: event.original_content || '',
          newContent: event.new_content || '',
        };
      } else if (confirmationType === 'exec') {
        // Exec confirmation (bash commands)
        confirmationData = {
          type: 'exec',
          tool_call_id: event.tool_call_id,
          tool_name: event.tool_name,
          tool_input: {
            command: event.command,
            description: event.description,
          },
          description: event.description,
          rootCommand: event.tool_name,
          command: event.command || '',
        };
      } else {
        // Info confirmation (generic)
        confirmationData = {
          type: 'info',
          tool_call_id: event.tool_call_id,
          tool_name: event.tool_name,
          tool_input: {
            command: event.command,
            description: event.description,
          },
          command: event.command,
          description: event.description,
        };
      }

      setPendingConfirmation(confirmationData);
      onConfirmationStart?.();
    },
    [onConfirmationStart]
  );

  // Confirm, reject, or reject_and_tell tool execution
  const confirmTool = useCallback(
    (outcome: ConfirmationOutcome, message?: string) => {
      if (!pendingConfirmation) return;

      const toolCallId = pendingConfirmation.tool_call_id;

      // Send response with new outcome field (and legacy approved for compatibility)
      connectionManager.send({
        type: 'TOOL_CONFIRMATION_RESPONSE',
        tool_call_id: toolCallId,
        outcome,  // New field: 'approve' | 'reject' | 'reject_and_tell'
        approved: outcome === 'approve',  // Legacy field for backward compatibility
        user_message: message,
        timestamp: new Date().toISOString(),
      });

      setPendingConfirmation(null);
      onConfirmationEnd?.(outcome);
    },
    [pendingConfirmation, connectionManager, onConfirmationEnd]
  );

  // Clear confirmation without sending response
  const clearConfirmation = useCallback(() => {
    setPendingConfirmation(null);
  }, []);

  return {
    pendingConfirmation,
    handleToolConfirmationRequest,
    confirmTool,
    clearConfirmation,
  };
}
