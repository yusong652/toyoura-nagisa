/**
 * Tool Confirmation Prompt Component
 * Reference: Gemini CLI ui/components/messages/ToolConfirmationMessage.tsx
 *
 * Displays a confirmation prompt for tool execution
 */

import React, { useCallback } from 'react';
import { Box, Text, useInput } from 'ink';
import type { ToolConfirmationData } from '../types.js';
import { theme } from '../colors.js';

interface ToolConfirmationPromptProps {
  data: ToolConfirmationData;
  onConfirm: (approved: boolean, message?: string) => void;
}

export const ToolConfirmationPrompt: React.FC<ToolConfirmationPromptProps> = ({
  data,
  onConfirm,
}) => {
  const handleConfirm = useCallback(
    (approved: boolean) => {
      onConfirm(approved);
    },
    [onConfirm],
  );

  useInput((input, key) => {
    if (input === 'y' || input === 'Y') {
      handleConfirm(true);
      return;
    }

    if (input === 'n' || input === 'N' || key.escape) {
      handleConfirm(false);
      return;
    }
  });

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={theme.status.warning}
      paddingX={1}
      marginY={1}
    >
      <Box marginBottom={1}>
        <Text bold color={theme.status.warning}>
          ? Tool Confirmation Required
        </Text>
      </Box>

      <Box flexDirection="column" marginBottom={1}>
        <Box>
          <Text color={theme.text.secondary}>Tool: </Text>
          <Text bold color={theme.text.primary}>
            {data.tool_name}
          </Text>
        </Box>

        {data.description && (
          <Box>
            <Text color={theme.text.secondary}>Description: </Text>
            <Text color={theme.text.muted}>{data.description}</Text>
          </Box>
        )}

        {data.command && (
          <Box marginTop={1}>
            <Text color={theme.text.muted}>{data.command}</Text>
          </Box>
        )}
      </Box>

      <Box>
        <Text color={theme.text.secondary}>
          Press <Text bold color={theme.status.success}>y</Text> to approve,{' '}
          <Text bold color={theme.status.error}>n</Text> or{' '}
          <Text bold color={theme.status.error}>Esc</Text> to reject
        </Text>
      </Box>
    </Box>
  );
};
