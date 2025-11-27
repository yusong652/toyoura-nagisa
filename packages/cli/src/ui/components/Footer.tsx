/**
 * Footer Component
 * Displays help hints and shortcuts
 */

import React from 'react';
import { Box, Text } from 'ink';
import { theme } from '../colors.js';

export const Footer: React.FC = () => {
  return (
    <Box flexDirection="row" marginTop={1} justifyContent="space-between">
      <Box>
        <Text color={theme.text.muted}>
          /help for commands | Ctrl+C to cancel | Ctrl+D to quit
        </Text>
      </Box>
    </Box>
  );
};
