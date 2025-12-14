/**
 * Root App Component
 * Reference: Gemini CLI ui/App.tsx
 *
 * This is the main rendering component that handles:
 * - Layout selection based on app state
 * - Quitting display
 * - Streaming context provision
 */

import { Box, Text } from 'ink';
import { useAppState } from './contexts/AppStateContext.js';
import { StreamingContext } from './contexts/StreamingContext.js';
import { MainLayout } from './layouts/MainLayout.js';
import { theme } from './colors.js';
import { GradientText } from './components/GradientText.js';
import { selectLogo, normalizeLineWidths, minimalLogo } from './components/AsciiArt.js';
import { useTerminalSize } from './hooks/useTerminalSize.js';
import { useBracketedPaste } from './hooks/useBracketedPaste.js';
import { useTheme } from './hooks/useTheme.js';

export const App = () => {
  const appState = useAppState();
  const { columns: terminalWidth } = useTerminalSize();

  // Subscribe to theme changes - triggers re-render when theme changes
  const { themeName } = useTheme();

  // Enable bracketed paste mode for multiline content support
  useBracketedPaste();

  // Show quitting message with logo
  if (appState.isQuitting) {
    const rawLogo = selectLogo(terminalWidth);
    const isMinimal = rawLogo === minimalLogo;
    const logo = isMinimal ? rawLogo : normalizeLineWidths(rawLogo);

    return (
      <Box flexDirection="column" padding={1}>
        <GradientText>{logo}</GradientText>
        <Text color={theme.text.secondary}>Goodbye! See you next time~</Text>
      </Box>
    );
  }

  // Show error state
  if (appState.error) {
    return (
      <Box flexDirection="column" padding={1}>
        <Text color={theme.status.error}>Error: {appState.error}</Text>
      </Box>
    );
  }

  return (
    <StreamingContext.Provider value={appState.streamingState.state}>
      <MainLayout key={themeName} />
    </StreamingContext.Provider>
  );
};
