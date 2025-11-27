/**
 * Error Message Component
 * Reference: Gemini CLI ui/components/messages/ErrorMessage.tsx
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ErrorHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';

interface ErrorMessageProps {
  item: ErrorHistoryItem;
  terminalWidth?: number;
}

export const ErrorMessage: React.FC<ErrorMessageProps> = ({ item, terminalWidth }) => {
  const prefix = '✕ ';
  const prefixWidth = prefix.length;

  return (
    <Box flexDirection="row" marginBottom={1} width={terminalWidth}>
      <Box width={prefixWidth} flexShrink={0}>
        <Text color={theme.status.error}>{prefix}</Text>
      </Box>
      <Box flexGrow={1}>
        <Text wrap="wrap" color={theme.status.error}>
          {item.message}
        </Text>
      </Box>
    </Box>
  );
};
