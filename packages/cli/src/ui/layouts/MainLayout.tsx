/**
 * Main Layout Component
 * Reference: Gemini CLI layouts/DefaultAppLayout.tsx, components/MainContent.tsx
 *
 * Handles the main application layout:
 * - Header (status bar)
 * - History (committed messages in <Static>)
 * - Pending items (streaming messages outside <Static>)
 * - Input area
 * - Footer (connection status, session info)
 *
 * Key Architecture:
 * - <Static> renders committed history items (won't change)
 * - Pending items are rendered outside <Static> for real-time updates
 */

import React from 'react';
import { Box, Static } from 'ink';
import { useAppState, useAppActions } from '../contexts/AppStateContext.js';
import { HistoryItemDisplay } from '../components/messages/HistoryItemDisplay.js';
import { PendingItemDisplay } from '../components/messages/PendingItemDisplay.js';
import { InputPrompt } from '../components/InputPrompt.js';
import { Header } from '../components/Header.js';
import { Footer } from '../components/Footer.js';
import { LoadingIndicator } from '../components/LoadingIndicator.js';
import { ToolConfirmationPrompt } from '../components/ToolConfirmationPrompt.js';

export const MainLayout: React.FC = () => {
  const appState = useAppState();
  const appActions = useAppActions();

  return (
    <Box flexDirection="column" width="100%">
      {/* History - committed items in <Static> for performance */}
      <Static items={appState.history}>
        {(item) => <HistoryItemDisplay key={item.id} item={item} />}
      </Static>

      {/* Pending items - rendered outside <Static> for real-time updates */}
      {appState.pendingHistoryItems.length > 0 && (
        <Box flexDirection="column">
          {appState.pendingHistoryItems.map((item, index) => (
            <PendingItemDisplay key={`pending-${index}`} item={item} />
          ))}
        </Box>
      )}

      {/* Loading indicator when streaming but no pending items yet */}
      {appState.isStreaming && appState.pendingHistoryItems.length === 0 && (
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

      {/* Status bar - below input */}
      <Header />

      {/* Footer */}
      <Footer />
    </Box>
  );
};
