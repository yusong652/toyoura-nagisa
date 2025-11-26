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
 * - Slash commands with autocomplete support
 * - Dialog system for interactive command responses
 */

import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
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
import { ProfileSelectDialog } from '../components/ProfileSelectDialog.js';
import { useTerminalSize } from '../hooks/useTerminalSize.js';
import { useSlashCommandProcessor } from '../hooks/useSlashCommandProcessor.js';
import { useTextBuffer } from '../utils/text-buffer.js';
import { MessageType, type AgentProfileType } from '../types.js';

// Dialog types
type ActiveDialog = 'profile' | 'memory' | null;

export const MainLayout: React.FC = () => {
  const appState = useAppState();
  const appActions = useAppActions();
  const { stdout } = useStdout();
  const { columns: terminalWidth } = useTerminalSize();
  const isInitialMount = useRef(true);

  // Key to force re-mount of Static component on terminal resize
  const [historyRemountKey, setHistoryRemountKey] = useState(0);

  // Active dialog state
  const [activeDialog, setActiveDialog] = useState<ActiveDialog>(null);

  // Input buffer - created here to survive InputPrompt unmount/remount
  // This is the key pattern from gemini-cli to preserve state across dialogs
  const buffer = useTextBuffer();

  // Slash command processor context
  const commandProcessorContext = useMemo(() => ({
    ui: {
      addItem: (item: any, timestamp?: number) => {
        appActions.addHistoryItem(item, timestamp);
      },
      clear: appActions.clearHistory,
      setPendingItem: () => {},
      reloadCommands: () => {},
    },
    session: {
      currentSessionId: appState.currentSessionId,
      stats: { inputTokens: 0, outputTokens: 0, totalTokens: 0 },
    },
  }), [appActions, appState.currentSessionId]);

  // Initialize slash command processor
  const { commands, processCommand, commandContext } = useSlashCommandProcessor({
    context: commandProcessorContext,
  });

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

  // Handle profile selection from dialog
  const handleProfileSelect = useCallback((profile: AgentProfileType) => {
    appActions.setProfile(profile);
    appActions.addHistoryItem({
      type: MessageType.INFO,
      message: `Switched to ${profile} profile`,
    });
    setActiveDialog(null);
  }, [appActions]);

  // Handle dialog cancel
  const handleDialogCancel = useCallback(() => {
    setActiveDialog(null);
  }, []);

  // Handle slash command execution
  const handleSlashCommand = useCallback(async (name: string, args: string) => {
    const result = await processCommand(name, args);

    if (!result) return;

    // Handle different result types
    switch (result.type) {
      case 'message':
        appActions.addHistoryItem({
          type: result.messageType === 'error' ? MessageType.ERROR : MessageType.INFO,
          message: result.content,
        });
        break;

      case 'memory_toggle':
        appActions.setMemoryEnabled(result.enabled);
        appActions.addHistoryItem({
          type: MessageType.INFO,
          message: `Memory ${result.enabled ? 'enabled' : 'disabled'}`,
        });
        break;

      case 'quit':
        appActions.quit();
        break;

      case 'dialog':
        // Open the appropriate dialog
        if (result.dialog === 'profile') {
          setActiveDialog('profile');
        }
        break;

      case 'load_history':
        // Load history items
        for (const item of result.history) {
          appActions.addHistoryItem(item);
        }
        break;

      case 'submit_prompt':
        // Submit as a regular message
        appActions.sendMessage(result.content);
        break;

      default:
        break;
    }
  }, [processCommand, appActions]);

  // Check if a dialog is active
  const isDialogActive = activeDialog !== null;

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

      {/* Profile selection dialog */}
      {activeDialog === 'profile' && (
        <ProfileSelectDialog
          currentProfile={appState.currentProfile}
          onSelect={handleProfileSelect}
          onCancel={handleDialogCancel}
        />
      )}

      {/* Input area with slash command support */}
      {appState.isInputActive && !appState.pendingConfirmation && !isDialogActive && (
        <InputPrompt
          buffer={buffer}
          onSubmit={appActions.sendMessage}
          onSlashCommand={handleSlashCommand}
          slashCommands={commands}
          commandContext={commandContext}
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
