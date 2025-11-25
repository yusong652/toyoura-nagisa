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
 * - Terminal resize triggers history refresh to prevent rendering artifacts
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Box, Static, useStdout } from 'ink';
import ansiEscapes from 'ansi-escapes';
import { useAppState, useAppActions } from '../contexts/AppStateContext.js';
import { HistoryItemDisplay } from '../components/messages/HistoryItemDisplay.js';
import { PendingItemDisplay } from '../components/messages/PendingItemDisplay.js';
import { InputPrompt } from '../components/InputPrompt.js';
import { Header } from '../components/Header.js';
import { Footer } from '../components/Footer.js';
import { LoadingIndicator } from '../components/LoadingIndicator.js';
import { ToolConfirmationPrompt } from '../components/ToolConfirmationPrompt.js';
import { useTerminalSize } from '../hooks/useTerminalSize.js';

export const MainLayout: React.FC = () => {
  const appState = useAppState();
  const appActions = useAppActions();
  const { stdout } = useStdout();
  const { columns: terminalWidth } = useTerminalSize();
  const isInitialMount = useRef(true);

  // Key to force re-mount of Static component on terminal resize
  const [historyRemountKey, setHistoryRemountKey] = useState(0);

  // Refresh static content by clearing terminal and forcing re-render
  const refreshStatic = useCallback(() => {
    stdout.write(ansiEscapes.clearTerminal);
    setHistoryRemountKey((prev) => prev + 1);
  }, [stdout]);

  // Handle terminal resize with debounce
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }

    const handler = setTimeout(() => {
      refreshStatic();
    }, 300);

    return () => {
      clearTimeout(handler);
    };
  }, [terminalWidth, refreshStatic]);

  return (
    <Box flexDirection="column" width="100%">
      {/* History - committed items in <Static> for performance */}
      {/* Key changes on terminal resize to force re-render and fix artifacts */}
      <Static key={historyRemountKey} items={appState.history}>
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
