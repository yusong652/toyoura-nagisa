/**
 * App Header Component
 * Reference: Gemini CLI ui/components/AppHeader.tsx
 *
 * Displays ASCII art logo with gradient colors and tips on startup
 */

import React from 'react';
import { Box, Text } from 'ink';
import { GradientText } from './GradientText.js';
import { selectLogo, getAsciiArtWidth, minimalLogo } from './AsciiArt.js';
import { useTerminalSize } from '../hooks/useTerminalSize.js';
import { theme } from '../colors.js';

interface AppHeaderProps {
  /** Show tips section */
  showTips?: boolean;
}

export const AppHeader: React.FC<AppHeaderProps> = ({
  showTips = true,
}) => {
  const { columns: terminalWidth } = useTerminalSize();
  const logo = selectLogo(terminalWidth);
  const isMinimal = logo === minimalLogo;
  const logoWidth = isMinimal ? minimalLogo.length : getAsciiArtWidth(logo);

  return (
    <Box flexDirection="column" marginBottom={1}>
      {/* Logo */}
      <Box
        alignItems="flex-start"
        width={logoWidth}
        flexShrink={0}
        flexDirection="column"
      >
        <GradientText>{logo}</GradientText>
      </Box>

      {/* Tips */}
      {showTips && (
        <Box flexDirection="column" marginTop={isMinimal ? 1 : 0}>
          <Text color={theme.text.secondary}>Tips for getting started:</Text>
          <Text color={theme.text.muted}>
            {'  '}1. Ask questions, edit files, or run commands.
          </Text>
          <Text color={theme.text.muted}>
            {'  '}2. Use{' '}
            <Text color={theme.text.accent}>@file</Text>
            {' '}to mention files in your messages.
          </Text>
          <Text color={theme.text.muted}>
            {'  '}3. Type{' '}
            <Text color={theme.text.accent}>/help</Text>
            {' '}for available commands.
          </Text>
        </Box>
      )}
    </Box>
  );
};
