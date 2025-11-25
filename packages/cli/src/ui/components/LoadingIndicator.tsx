/**
 * Loading Indicator Component
 * Shows a spinner when the AI is responding
 */

import React from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import { theme } from '../colors.js';

interface LoadingIndicatorProps {
  thinkingContent?: string | null;
}

export const LoadingIndicator: React.FC<LoadingIndicatorProps> = ({
  thinkingContent,
}) => {
  return (
    <Box flexDirection="column" marginY={1}>
      <Box flexDirection="row">
        <Text color={theme.ui.spinner}>
          <Spinner type="dots" />
        </Text>
        <Text color={theme.text.muted}> Thinking...</Text>
      </Box>
      {thinkingContent && (
        <Box marginLeft={2} marginTop={1}>
          <Text color={theme.message.thinking} dimColor>
            {thinkingContent}
          </Text>
        </Box>
      )}
    </Box>
  );
};
