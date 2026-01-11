/**
 * Shell Command Message Component
 * Displays user shell commands (! prefix) with distinct styling
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ShellCommandHistoryItem } from '../../types.js';
import { colors } from '../../colors.js';

interface ShellCommandMessageProps {
  item: ShellCommandHistoryItem;
  terminalWidth?: number;
}

export const ShellCommandMessage: React.FC<ShellCommandMessageProps> = ({ item, terminalWidth }) => {
  const prefix = '! ';

  return (
    <Box marginBottom={0} width={terminalWidth}>
      <Text color={colors.primary} bold>{prefix}</Text>
      <Text color={colors.primary}>{item.command}</Text>
    </Box>
  );
};
