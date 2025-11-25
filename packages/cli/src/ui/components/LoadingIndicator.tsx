/**
 * Loading Indicator Component
 * Reference: Gemini CLI ui/components/GeminiRespondingSpinner.tsx
 *
 * Shows a spinner when the AI is responding, with optional thinking content.
 * Uses the ✦ prefix to match Gemini CLI style.
 */

import React from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import { theme } from '../colors.js';

interface LoadingIndicatorProps {
  thinkingContent?: string | null;
  message?: string;
}

// Maximum lines of thinking content to show
const MAX_THINKING_LINES = 5;

/**
 * Truncate thinking content to avoid overwhelming the display
 */
function truncateThinking(content: string, maxLines: number): string {
  const lines = content.split('\n');
  if (lines.length <= maxLines) {
    return content;
  }
  return lines.slice(-maxLines).join('\n'); // Show last N lines (most recent)
}

export const LoadingIndicator: React.FC<LoadingIndicatorProps> = ({
  thinkingContent,
  message = 'Thinking...',
}) => {
  const prefix = '✦ ';
  const prefixWidth = 2;

  return (
    <Box flexDirection="column" marginY={1}>
      <Box flexDirection="row">
        <Box width={prefixWidth} flexShrink={0}>
          <Text color={theme.text.accent}>{prefix}</Text>
        </Box>
        <Box flexDirection="row">
          <Text color={theme.ui.spinner}>
            <Spinner type="dots" />
          </Text>
          <Text color={theme.text.muted}> {message}</Text>
        </Box>
      </Box>
      {thinkingContent && (
        <Box marginLeft={prefixWidth}>
          <Text color={theme.message.thinking} dimColor wrap="wrap">
            {truncateThinking(thinkingContent, MAX_THINKING_LINES)}
          </Text>
        </Box>
      )}
    </Box>
  );
};
