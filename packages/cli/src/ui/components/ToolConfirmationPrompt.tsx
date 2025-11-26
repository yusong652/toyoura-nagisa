/**
 * Tool Confirmation Prompt Component
 * Reference: Gemini CLI ui/components/messages/ToolConfirmationMessage.tsx
 *
 * Displays a confirmation prompt for tool execution with keyboard navigation.
 * Uses RadioButtonSelect for up/down arrow key selection.
 */

import React, { useCallback, useMemo } from 'react';
import { Box, Text } from 'ink';
import type { ToolConfirmationData } from '../types.js';
import { theme } from '../colors.js';
import { RadioButtonSelect, type RadioSelectItem } from './shared/RadioButtonSelect.js';
import { useKeypress } from '../hooks/useKeypress.js';

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

      {/* Tool Info */}
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

      {data.command && (
        <Box>
          <Text color={theme.text.secondary}>{data.command}</Text>
        </Box>
      )}

      {/* Question */}
      <Box marginTop={1}>
        <Text color={theme.text.primary}>Allow execution?</Text>
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
