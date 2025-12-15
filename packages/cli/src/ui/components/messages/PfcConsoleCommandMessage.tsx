/**
 * PFC Console Command Message Component
 * Displays user PFC Python commands (> prefix) with distinct styling
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { PfcConsoleCommandHistoryItem } from '../../types.js';
import { theme, colors } from '../../colors.js';

interface PfcConsoleCommandMessageProps {
  item: PfcConsoleCommandHistoryItem;
  terminalWidth?: number;
}

export const PfcConsoleCommandMessage: React.FC<PfcConsoleCommandMessageProps> = ({ item, terminalWidth }) => {
  // Use "py>" prefix to indicate PFC Python console
  const prefix = 'py> ';

  return (
    <Box marginBottom={1} width={terminalWidth}>
      <Text backgroundColor={colors.bgLight}>
        <Text color={theme.status.info} bold>{prefix}</Text>
        <Text color={theme.status.info}>{item.code}</Text>
      </Text>
    </Box>
  );
};
