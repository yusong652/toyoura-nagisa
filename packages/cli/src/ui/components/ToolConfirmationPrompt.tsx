/**
 * Tool Confirmation Prompt Component
 * Reference: Gemini CLI ui/components/messages/ToolConfirmationMessage.tsx
 *
 * Displays a confirmation prompt for tool execution with keyboard navigation.
 * Supports different confirmation types:
 * - edit: Shows git diff-style visualization for file changes
 * - exec: Shows command to be executed
 * - info: Generic tool confirmation
 *
 * Confirmation outcomes:
 * - approve: Execute the tool
 * - reject: Stop execution, user wants to provide input via main input
 * - reject_and_tell: Continue execution with user's brief instruction
 */

import React, { useCallback, useMemo, useState } from 'react';
import { Box, Text, useStdout, useInput } from 'ink';
import TextInput from 'ink-text-input';
import type {
  ToolConfirmationData,
  EditToolConfirmationData,
  ExecToolConfirmationData,
  InfoToolConfirmationData,
} from '../types.js';
import { theme } from '../colors.js';
import { RadioButtonSelect, type RadioSelectItem } from './shared/RadioButtonSelect.js';
import { useKeypress } from '../hooks/useKeypress.js';
import { DiffRenderer, getDiffStats } from './DiffRenderer.js';

// Confirmation outcome types matching backend
export type ConfirmationOutcome = 'approve' | 'reject' | 'reject_and_tell';

interface ToolConfirmationPromptProps {
  data: ToolConfirmationData;
  onConfirm: (outcome: ConfirmationOutcome, message?: string) => void;
  isFocused?: boolean;
}

// Radio option type (without reject_and_tell input mode)
type RadioOutcome = 'approve' | 'reject' | 'reject_and_tell';

export const ToolConfirmationPrompt: React.FC<ToolConfirmationPromptProps> = ({
  data,
  onConfirm,
  isFocused = true,
}) => {
  const { stdout } = useStdout();
  const terminalWidth = stdout?.columns ?? 80;
  const terminalHeight = stdout?.rows ?? 24;

  // State for "reject and tell" input mode
  const [isInputMode, setIsInputMode] = useState(false);
  const [inputValue, setInputValue] = useState('');

  const handleSelect = useCallback(
    (outcome: RadioOutcome) => {
      if (outcome === 'reject_and_tell') {
        // Enter input mode for user instruction
        setIsInputMode(true);
      } else {
        onConfirm(outcome);
      }
    },
    [onConfirm]
  );

  const handleInputSubmit = useCallback(
    (value: string) => {
      // Submit the reject_and_tell with user's instruction
      onConfirm('reject_and_tell', value.trim() || undefined);
    },
    [onConfirm]
  );

  const handleInputCancel = useCallback(() => {
    // Cancel input mode, go back to radio selection
    setIsInputMode(false);
    setInputValue('');
  }, []);

  // Calculate available height for diff content
  // We need to reserve space for:
  // - Outer border (2 lines: top + bottom)
  // - Header "Tool Confirmation Required" (1 line + 1 margin)
  // - File info line (1 line + 1 margin)
  // - Diff border (2 lines: top + bottom)
  // - Question line (1 line + 1 margin)
  // - Radio options (2 lines)
  // - Help text (1 line + 1 margin)
  // Total fixed UI: ~14 lines minimum
  const UI_CHROME_HEIGHT = 14;

  const availableHeight = useMemo(() => {
    const confirmationType = (data as { type?: string }).type;
    if (confirmationType === 'edit') {
      // Ensure at least 3 lines for diff content
      return Math.max(3, terminalHeight - UI_CHROME_HEIGHT);
    }
    return 0;
  }, [data, terminalHeight]);

  // Handle escape key in radio mode using custom keypress handler
  useKeypress(
    (key) => {
      if (!isFocused || isInputMode) return;

      // Escape or Ctrl+C to reject (only in radio mode)
      if (key.name === 'escape' || (key.ctrl && key.name === 'c')) {
        onConfirm('reject');
        return;
      }
    },
    { isActive: isFocused && !isInputMode }
  );

  // Handle escape key in input mode using ink's useInput (compatible with TextInput)
  useInput(
    (_input, key) => {
      if (!isFocused || !isInputMode) return;

      if (key.escape) {
        handleInputCancel();
      }
    },
    { isActive: isFocused && isInputMode }
  );

  const options: Array<RadioSelectItem<RadioOutcome>> = useMemo(
    () => [
      {
        label: 'Yes, allow',
        value: 'approve' as const,
        key: 'approve',
      },
      {
        label: 'No, reject (Esc)',
        value: 'reject' as const,
        key: 'reject',
      },
      {
        label: 'Reject and tell agent...',
        value: 'reject_and_tell' as const,
        key: 'reject_and_tell',
      },
    ],
    []
  );

  // Render content based on confirmation type
  const { bodyContent, question } = useMemo(() => {
    let bodyContent: React.ReactNode = null;
    let question = 'Allow execution?';

    // Type guard to check confirmation type
    const confirmationType = (data as { type?: string }).type;

    if (confirmationType === 'edit') {
      const editData = data as EditToolConfirmationData;
      const diffStats = getDiffStats(editData.fileDiff);
      const isNewFile = editData.originalContent === '';

      question = 'Apply this change?';
      bodyContent = (
        <Box flexDirection="column">
          {/* File header with stats */}
          <Box flexDirection="row" gap={1}>
            <Text color={theme.text.link} bold>
              {editData.fileName}
            </Text>
            {isNewFile ? (
              <Text color={theme.status.success} dimColor>(new file)</Text>
            ) : (
              <>
                <Text color={theme.status.success}>+{diffStats.additions}</Text>
                <Text color={theme.status.error}>-{diffStats.deletions}</Text>
              </>
            )}
          </Box>

          {/* Diff content - clean, no extra border */}
          <Box marginTop={1} flexDirection="column">
            <DiffRenderer
              diffContent={editData.fileDiff}
              filename={editData.fileName}
              maxWidth={terminalWidth - 4}
              maxHeight={availableHeight}
            />
          </Box>
        </Box>
      );
    } else if (confirmationType === 'exec') {
      const execData = data as ExecToolConfirmationData;
      question = `Allow execution of: '${execData.rootCommand}'?`;
      bodyContent = (
        <Box
          borderStyle="round"
          borderColor={theme.border.default}
          paddingX={1}
        >
          <Text color={theme.text.link} wrap="wrap">
            {execData.command}
          </Text>
        </Box>
      );
    } else if (confirmationType === 'info') {
      const infoData = data as InfoToolConfirmationData;
      question = 'Do you want to proceed?';
      bodyContent = (
        <Box flexDirection="column">
          <Box>
            <Text color={theme.text.muted}>Tool: </Text>
            <Text bold color={theme.text.primary}>
              {infoData.tool_name}
            </Text>
          </Box>
          {infoData.description && (
            <Box>
              <Text color={theme.text.muted}>Description: </Text>
              <Text color={theme.text.secondary}>{infoData.description}</Text>
            </Box>
          )}
          {infoData.command && (
            <Box marginTop={1}>
              <Text color={theme.text.secondary}>{infoData.command}</Text>
            </Box>
          )}
        </Box>
      );
    } else {
      // Legacy format without type field - use generic display
      bodyContent = (
        <Box flexDirection="column">
          <Box>
            <Text color={theme.text.muted}>Tool: </Text>
            <Text bold color={theme.text.primary}>
              {data.tool_name}
            </Text>
          </Box>
          {data.description && (
            <Box>
              <Text color={theme.text.muted}>Description: </Text>
              <Text color={theme.text.secondary}>{data.description}</Text>
            </Box>
          )}
          {(data as InfoToolConfirmationData).command && (
            <Box marginTop={1}>
              <Text color={theme.text.secondary}>
                {(data as InfoToolConfirmationData).command}
              </Text>
            </Box>
          )}
        </Box>
      );
    }

    return { bodyContent, question };
  }, [data, terminalWidth, availableHeight]);

  // Calculate maximum height for the entire component
  // This ensures the component never exceeds terminal height
  const maxComponentHeight = Math.max(UI_CHROME_HEIGHT, terminalHeight - 2);

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={theme.border.focused}
      paddingX={1}
      maxHeight={maxComponentHeight}
      overflow="hidden"
    >
      {/* Header - fixed height, never shrinks */}
      <Box marginBottom={1} flexShrink={0}>
        <Text color={theme.text.accent}>? </Text>
        <Text bold color={theme.text.primary}>
          Tool Confirmation Required
        </Text>
      </Box>

      {/* Body Content (Diff or Command) - can shrink if needed */}
      <Box flexGrow={1} flexShrink={1} marginBottom={1} overflow="hidden">
        {bodyContent}
      </Box>

      {/* Question - fixed height, never shrinks */}
      <Box marginBottom={1} flexShrink={0}>
        <Text color={theme.text.primary}>{question}</Text>
      </Box>

      {/* Radio Button Select or Input Mode */}
      <Box flexShrink={0}>
        {isInputMode ? (
          // Input mode for "reject and tell"
          <Box flexDirection="column">
            <Box marginBottom={1}>
              <Text color={theme.text.accent}>
                Tell the agent what to do instead:
              </Text>
            </Box>
            <Box>
              <Text color={theme.text.muted}>{'> '}</Text>
              <TextInput
                value={inputValue}
                onChange={setInputValue}
                onSubmit={handleInputSubmit}
                focus={isFocused}
                placeholder="e.g., use a different approach..."
              />
            </Box>
          </Box>
        ) : (
          // Radio button selection
          <RadioButtonSelect
            items={options}
            onSelect={handleSelect}
            isFocused={isFocused}
            showNumbers={true}
          />
        )}
      </Box>

      {/* Help text - fixed height, never shrinks */}
      <Box marginTop={1} flexShrink={0}>
        <Text color={theme.text.muted}>
          {isInputMode
            ? '(Enter submit, Esc cancel)'
            : '(↑↓ select, Enter confirm, Esc cancel)'}
        </Text>
      </Box>
    </Box>
  );
};
