/**
 * Tool Confirmation Prompt Component
 * Reference: Gemini CLI ui/components/messages/ToolConfirmationMessage.tsx
 *
 * Displays a confirmation prompt for tool execution with keyboard navigation.
 * Supports different confirmation types:
 * - edit: Shows git diff-style visualization for file changes
 * - exec: Shows command to be executed
 * - info: Generic tool confirmation
 */

import React, { useCallback, useMemo } from 'react';
import { Box, Text, useStdout } from 'ink';
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

interface ToolConfirmationPromptProps {
  data: ToolConfirmationData;
  onConfirm: (approved: boolean, message?: string) => void;
  isFocused?: boolean;
}

type ConfirmationOutcome = 'approve' | 'reject';

export const ToolConfirmationPrompt: React.FC<ToolConfirmationPromptProps> = ({
  data,
  onConfirm,
  isFocused = true,
}) => {
  const { stdout } = useStdout();
  const terminalWidth = stdout?.columns ?? 80;
  const terminalHeight = stdout?.rows ?? 24;

  const handleSelect = useCallback(
    (outcome: ConfirmationOutcome) => {
      onConfirm(outcome === 'approve');
    },
    [onConfirm]
  );

  // Handle escape key to reject
  useKeypress(
    (key) => {
      if (!isFocused) return;
      if (key.name === 'escape' || (key.ctrl && key.name === 'c')) {
        onConfirm(false);
      }
    },
    { isActive: isFocused }
  );

  const options: Array<RadioSelectItem<ConfirmationOutcome>> = useMemo(
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

      // Calculate available height for diff (reserve space for UI elements)
      const headerHeight = 4;  // Header + stats
      const questionHeight = 3; // Question + options
      const helpHeight = 2;    // Help text + margin
      const availableHeight = Math.max(5, terminalHeight - headerHeight - questionHeight - helpHeight - 4);

      question = 'Apply this change?';
      bodyContent = (
        <Box flexDirection="column">
          {/* File info and stats */}
          <Box marginBottom={1} flexDirection="row" gap={2}>
            <Text color={theme.text.accent} bold>
              {editData.fileName}
            </Text>
            {!isNewFile && (
              <Box flexDirection="row" gap={1}>
                <Text color={theme.status.success}>+{diffStats.additions}</Text>
                <Text color={theme.status.error}>-{diffStats.deletions}</Text>
              </Box>
            )}
            {isNewFile && (
              <Text color={theme.status.success}>(new file)</Text>
            )}
          </Box>

          {/* Diff content */}
          <Box
            borderStyle="round"
            borderColor={theme.border.default}
            paddingX={1}
            flexDirection="column"
          >
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
  }, [data, terminalWidth, terminalHeight]);

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={theme.border.focused}
      paddingX={1}
    >
      {/* Header */}
      <Box marginBottom={1}>
        <Text color={theme.text.accent}>? </Text>
        <Text bold color={theme.text.primary}>
          Tool Confirmation Required
        </Text>
      </Box>

      {/* Body Content (Diff or Command) */}
      <Box flexGrow={1} marginBottom={1}>
        {bodyContent}
      </Box>

      {/* Question */}
      <Box marginBottom={1}>
        <Text color={theme.text.primary}>{question}</Text>
      </Box>

      {/* Radio Button Select */}
      <RadioButtonSelect
        items={options}
        onSelect={handleSelect}
        isFocused={isFocused}
        showNumbers={true}
      />

      {/* Help text */}
      <Box marginTop={1}>
        <Text color={theme.text.muted}>
          (Use arrows to navigate, Enter to select, Esc to cancel)
        </Text>
      </Box>
    </Box>
  );
};
