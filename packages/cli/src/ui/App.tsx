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

export const App = () => {
  const appState = useAppState();

  // Show quitting message
  if (appState.isQuitting) {
    return (
      <Box flexDirection="column" padding={1}>
        <Text color={theme.text.secondary}>Goodbye! 👋</Text>
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
    <StreamingContext.Provider value={appState.streamingState}>
      <MainLayout />
    </StreamingContext.Provider>
  );
};
