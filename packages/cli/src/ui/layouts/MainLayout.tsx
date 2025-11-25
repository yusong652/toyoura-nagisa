/**
 * Main Layout Component
 * Reference: Gemini CLI layouts/DefaultAppLayout.tsx
 *
 * Handles the main application layout:
 * - Header (status bar)
 * - History (messages)
 * - Input area
 * - Footer (connection status, session info)
 */

import React from 'react';
import { Box, Static, Text } from 'ink';
import { useAppState, useAppActions } from '../contexts/AppStateContext.js';
import { HistoryItemDisplay } from '../components/messages/HistoryItemDisplay.js';
import { InputPrompt } from '../components/InputPrompt.js';
import { Header } from '../components/Header.js';
import { Footer } from '../components/Footer.js';
import { LoadingIndicator } from '../components/LoadingIndicator.js';
import { ToolConfirmationPrompt } from '../components/ToolConfirmationPrompt.js';
import { theme } from '../colors.js';

export const MainLayout: React.FC = () => {
  const appState = useAppState();
  const appActions = useAppActions();

  return (
    <Box flexDirection="column" width="100%">
      {/* Header */}
      <Header />

      {/* History - using Static for performance */}
      <Static items={appState.history}>
        {(item) => <HistoryItemDisplay key={item.id} item={item} />}
      </Static>

      {/* Loading indicator when streaming */}
      {appState.isStreaming && (
        <LoadingIndicator
          thinkingContent={appState.streamingState.thinkingContent}
        />
      )}

      {/* Tool confirmation dialog */}
      {appState.pendingConfirmation && (
        <ToolConfirmationPrompt
          data={appState.pendingConfirmation}
          onConfirm={appActions.confirmTool}
        />
      )}

      {/* Input area */}
      {appState.isInputActive && !appState.pendingConfirmation && (
        <InputPrompt
          onSubmit={appActions.sendMessage}
          disabled={appState.isStreaming}
        />
      )}

      {/* Footer */}
      <Footer />
    </Box>
  );
};
