/**
 * Main Layout Component
 * Reference: Gemini CLI layouts/DefaultAppLayout.tsx, components/MainContent.tsx
 *
 * Handles the main application layout:
 * - Header (status bar)
 * - History (committed messages)
 * - Pending items (streaming messages)
 * - Input area
 * - Footer (connection status, session info)
 *
 * Key Architecture:
 * - Uses Ink's Static component to render history to terminal's main buffer
 * - This enables native terminal scrolling and text selection
 * - Terminal resize triggers history refresh to prevent rendering artifacts
 * - Slash commands with autocomplete support
 * - Dialog system for interactive command responses
 */

import React, { useState, useEffect, useCallback, useMemo, useRef, memo } from 'react';
import { Box, Static } from 'ink';
import { useAppState, useAppActions } from '../contexts/AppStateContext.js';
import { HistoryItemDisplay } from '../components/messages/HistoryItemDisplay.js';
import { PendingItemDisplay } from '../components/messages/PendingItemDisplay.js';
import { InputPrompt } from '../components/InputPrompt.js';
import { Header } from '../components/Header.js';
import { AppHeader } from '../components/AppHeader.js';
import { LoadingIndicator } from '../components/LoadingIndicator.js';
import { TodoStatusIndicator } from '../components/TodoStatusIndicator.js';
import { ToolConfirmationPrompt } from '../components/ToolConfirmationPrompt.js';
import { SelectDialog, type SelectOption } from '../components/SelectDialog.js';
import { FullContextView } from '../components/FullContextView.js';
import { useTerminalSize } from '../hooks/useTerminalSize.js';
import { useSlashCommandProcessor } from '../hooks/useSlashCommandProcessor.js';
import { useSessionManager } from '../hooks/useSessionManager.js';
import { useShellCommand } from '../hooks/useShellCommand.js';
import { useTextBuffer } from '../utils/text-buffer.js';
import { MessageType, type AgentProfileType } from '../types.js';
import { theme, themeManager } from '../colors.js';
import { themes, type ThemeName } from '../themes/index.js';

// Memoized components for performance
const MemoizedHistoryItemDisplay = memo(HistoryItemDisplay);
const MemoizedAppHeader = memo(AppHeader);

// Dialog types
type ActiveDialog = 'profile' | 'memory' | 'session' | 'session_restore' | 'session_delete' | 'theme' | null;

// Session action type
type SessionAction = 'create' | 'restore' | 'delete';

// Profile options for SelectDialog
const PROFILE_OPTIONS: SelectOption<AgentProfileType>[] = [
  { key: 'coding', value: 'coding', label: 'Coding', description: 'Code development and programming tasks' },
  { key: 'lifestyle', value: 'lifestyle', label: 'Lifestyle', description: 'Daily life, email, calendar, and communication' },
  { key: 'pfc', value: 'pfc', label: 'PFC', description: 'ITASCA PFC simulation specialist' },
  { key: 'general', value: 'general', label: 'General', description: 'Full tool capabilities for complex tasks' },
  { key: 'disabled', value: 'disabled', label: 'Disabled', description: 'Pure text conversation mode (no tools)' },
];

// Memory options for SelectDialog
const MEMORY_OPTIONS: SelectOption<boolean>[] = [
  { key: 'on', value: true, label: 'On', description: 'AI can recall previous conversations' },
  { key: 'off', value: false, label: 'Off', description: 'No long-term memory, fresh context each time' },
];

// Session action options for SelectDialog
const SESSION_ACTION_OPTIONS: SelectOption<SessionAction>[] = [
  { key: 'create', value: 'create', label: 'Create', description: 'Create a new chat session' },
  { key: 'restore', value: 'restore', label: 'Restore', description: 'Switch to an existing session' },
  { key: 'delete', value: 'delete', label: 'Delete', description: 'Delete an existing session' },
];

// Theme options for SelectDialog
const THEME_OPTIONS: SelectOption<ThemeName>[] = Object.entries(themes).map(([key, def]) => ({
  key,
  value: key as ThemeName,
  label: def.displayName,
  description: def.description,
}));

export const MainLayout: React.FC = () => {
  const appState = useAppState();
  const appActions = useAppActions();
  const { columns: terminalWidth } = useTerminalSize();

  // Track previous width to detect actual changes
  const previousWidthRef = useRef(terminalWidth);
  const resizeTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Key to force re-render of history on terminal resize
  const [renderKey, setRenderKey] = useState(0);

  // Active dialog state
  const [activeDialog, setActiveDialog] = useState<ActiveDialog>(null);

  // Calculate input width (terminal width minus border and padding)
  // Border: 2 (left + right), Padding: 2 (left + right), Prefix: 2 ("> ")
  const inputWidth = Math.max(1, terminalWidth - 6);

  // Input buffer - created here to survive InputPrompt unmount/remount
  // This is the key pattern from gemini-cli to preserve state across dialogs
  const buffer = useTextBuffer({ viewportWidth: inputWidth });

  // Session manager for API calls
  const sessionManager = useSessionManager();

  // Shell command execution
  const { executeCommand: executeShellCommand, isExecuting: isShellExecuting, cwd: shellCwd } = useShellCommand(
    appState.currentSessionId,
    appState.currentProfile
  );

  // Shell mode state (for UI indicator)
  const [isShellMode, setIsShellMode] = useState(false);

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

  // Handle terminal resize - force re-render to fix layout artifacts
  useEffect(() => {
    // Only process if width actually changed
    if (previousWidthRef.current === terminalWidth) {
      return;
    }
    previousWidthRef.current = terminalWidth;

    // Clear any pending timeout
    if (resizeTimeoutRef.current) {
      clearTimeout(resizeTimeoutRef.current);
    }

    // Debounce: wait for resize to settle before refreshing
    resizeTimeoutRef.current = setTimeout(() => {
      setRenderKey((prev) => prev + 1);
      resizeTimeoutRef.current = null;
    }, 150);

    return () => {
      if (resizeTimeoutRef.current) {
        clearTimeout(resizeTimeoutRef.current);
        resizeTimeoutRef.current = null;
      }
    };
  }, [terminalWidth]);

  // Update text buffer viewport width when terminal size changes
  useEffect(() => {
    buffer.setViewportWidth(inputWidth);
  }, [inputWidth, buffer]);

  // Handle profile selection from dialog
  const handleProfileSelect = useCallback((profile: AgentProfileType) => {
    appActions.setProfile(profile);
    appActions.addHistoryItem({
      type: MessageType.INFO,
      message: `Switched to ${profile} profile`,
    });
    setActiveDialog(null);
  }, [appActions]);

  // Handle memory selection from dialog
  const handleMemorySelect = useCallback((enabled: boolean) => {
    appActions.setMemoryEnabled(enabled);
    appActions.addHistoryItem({
      type: MessageType.INFO,
      message: `Memory ${enabled ? 'enabled' : 'disabled'}`,
    });
    setActiveDialog(null);
  }, [appActions]);

  // Handle theme selection from dialog
  const handleThemeSelect = useCallback((themeName: ThemeName) => {
    themeManager.setTheme(themeName);
    const selectedTheme = themes[themeName];
    appActions.addHistoryItem({
      type: MessageType.INFO,
      message: `Switched to ${selectedTheme.displayName} theme`,
    });
    setActiveDialog(null);
    // In alternate buffer mode, Ink handles re-rendering automatically
  }, [appActions]);

  // Handle dialog cancel
  const handleDialogCancel = useCallback(() => {
    setActiveDialog(null);
  }, []);

  // Handle session action selection (create/restore/delete)
  const handleSessionActionSelect = useCallback(async (action: SessionAction) => {
    switch (action) {
      case 'create': {
        try {
          const sessionId = await appActions.createSession();
          appActions.addHistoryItem({
            type: MessageType.INFO,
            message: `Created new session: ${sessionId.slice(0, 8)}...`,
          });
        } catch (e) {
          appActions.addHistoryItem({
            type: MessageType.ERROR,
            message: e instanceof Error ? e.message : 'Failed to create session',
          });
        }
        setActiveDialog(null);
        break;
      }
      case 'restore':
        // Load sessions and show restore dialog
        await sessionManager.loadSessions();
        setActiveDialog('session_restore');
        break;
      case 'delete':
        // Load sessions and show delete dialog
        await sessionManager.loadSessions();
        setActiveDialog('session_delete');
        break;
    }
  }, [sessionManager, appActions]);

  // Handle session restore selection
  const handleSessionRestoreSelect = useCallback(async (sessionId: string) => {
    // Skip if selecting current session
    if (sessionId === appState.currentSessionId) {
      return;
    }

    try {
      await appActions.switchSession(sessionId);
      const session = sessionManager.sessions.find(s => s.id === sessionId);
      appActions.addHistoryItem({
        type: MessageType.INFO,
        message: `Restored session: ${session?.name || sessionId}`,
      });
    } catch (e) {
      appActions.addHistoryItem({
        type: MessageType.ERROR,
        message: e instanceof Error ? e.message : 'Failed to restore session',
      });
    }
    setActiveDialog(null);
  }, [sessionManager, appActions, appState.currentSessionId]);

  // Handle session delete selection
  const handleSessionDeleteSelect = useCallback(async (sessionId: string) => {
    const session = sessionManager.sessions.find(s => s.id === sessionId);
    const success = await sessionManager.deleteSession(sessionId);
    if (success) {
      appActions.addHistoryItem({
        type: MessageType.INFO,
        message: `Deleted session: ${session?.name || sessionId}`,
      });
    } else {
      appActions.addHistoryItem({
        type: MessageType.ERROR,
        message: sessionManager.error || 'Failed to delete session',
      });
    }
    setActiveDialog(null);
  }, [sessionManager, appActions]);

  // Handle shell command blocked during streaming
  const handleShellBlocked = useCallback(() => {
    appActions.addHistoryItem({
      type: MessageType.ERROR,
      message: 'Shell commands are disabled while AI is responding. Please wait.',
    });
  }, [appActions]);

  // Handle shell command execution (! prefix)
  const handleShellCommand = useCallback(async (command: string) => {
    // Add user's shell command to history with distinct styling
    appActions.addHistoryItem({
      type: MessageType.SHELL_COMMAND,
      command: command,
    });

    // Execute the shell command
    const result = await executeShellCommand(command);

    if (result) {
      // Add shell result with distinct styling
      appActions.addHistoryItem({
        type: MessageType.SHELL_RESULT,
        stdout: result.stdout || '',
        stderr: result.stderr || '',
        exitCode: result.exit_code,
        isError: !result.success,
      });
    } else {
      appActions.addHistoryItem({
        type: MessageType.ERROR,
        message: 'Failed to execute shell command',
      });
    }
  }, [appActions, executeShellCommand]);

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
        } else if (result.dialog === 'memory') {
          setActiveDialog('memory');
        } else if (result.dialog === 'session') {
          setActiveDialog('session');
        } else if (result.dialog === 'theme') {
          setActiveDialog('theme');
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

  // Build static items for history (rendered once to terminal buffer)
  // Using Static component enables native terminal scrolling and text selection
  // NOTE: AppHeader is rendered separately outside Static to avoid rendering issues
  // when items are removed from Static (Ink's Static doesn't clear previous output)
  const staticItems = useMemo(() => {
    return appState.history.map((item) => (
      <MemoizedHistoryItemDisplay key={item.id} item={item} />
    ));
  }, [appState.history]);

  // Show welcome header only when no history and not streaming
  const showWelcomeHeader = appState.history.length === 0 && !appState.isStreaming;

  // Pending items component (dynamically updated, not in Static)
  const pendingItems = useMemo(
    () => (
      <Box flexDirection="column">
        {appState.pendingHistoryItems.map((item, index) => (
          <PendingItemDisplay key={`pending-${index}`} item={item} />
        ))}
        {/* Loading indicator when streaming but no pending items yet */}
        {appState.isStreaming && appState.pendingHistoryItems.length === 0 && (
          <LoadingIndicator
            thinkingContent={appState.streamingState.thinkingContent}
          />
        )}
      </Box>
    ),
    [appState.pendingHistoryItems, appState.isStreaming, appState.streamingState.thinkingContent],
  );

  // Full context view mode - shows overlay with complete history
  if (appState.isFullContextMode) {
    return (
      <FullContextView onClose={appActions.toggleFullContextMode} />
    );
  }

  return (
    <Box flexDirection="column" width="100%">
      {/* Welcome header - rendered outside Static to avoid removal issues */}
      {/* Ink's Static doesn't clear previous output when items are removed */}
      {showWelcomeHeader && <MemoizedAppHeader showTips={true} />}

      {/* Static content area - rendered once to terminal buffer */}
      {/* Key changes on resize to force re-render and fix layout artifacts */}
      <Static key={renderKey} items={staticItems}>
        {(item) => item}
      </Static>

      {/* Dynamic pending items - updated during streaming */}
      {pendingItems}

      {/* Bottom controls */}
      <Box flexDirection="column">
        {/* Tool confirmation dialog */}
        {appState.pendingConfirmation && (
          <ToolConfirmationPrompt
            data={appState.pendingConfirmation}
            onConfirm={appActions.confirmTool}
          />
        )}

        {/* Profile selection dialog */}
        {activeDialog === 'profile' && (
          <SelectDialog
            title="Select Agent Profile"
            description="Choose a profile to optimize tool loading for your task:"
            options={PROFILE_OPTIONS}
            currentValue={appState.currentProfile}
            onSelect={handleProfileSelect}
            onCancel={handleDialogCancel}
            showNumbers={true}
          />
        )}

        {/* Memory selection dialog */}
        {activeDialog === 'memory' && (
          <SelectDialog
            title="Toggle Memory"
            description="Enable or disable long-term conversation memory:"
            options={MEMORY_OPTIONS}
            currentValue={appState.memoryEnabled}
            onSelect={handleMemorySelect}
            onCancel={handleDialogCancel}
          />
        )}

        {/* Theme selection dialog */}
        {activeDialog === 'theme' && (
          <SelectDialog
            title="Select Theme"
            description="Choose a color theme:"
            options={THEME_OPTIONS}
            currentValue={themeManager.getCurrentThemeName()}
            onSelect={handleThemeSelect}
            onCancel={handleDialogCancel}
            showNumbers={true}
          />
        )}

        {/* Session action dialog */}
        {activeDialog === 'session' && (
          <SelectDialog
            title="Session Management"
            description="Choose an action:"
            options={SESSION_ACTION_OPTIONS}
            onSelect={handleSessionActionSelect}
            onCancel={handleDialogCancel}
          />
        )}

        {/* Session restore dialog */}
        {activeDialog === 'session_restore' && (
          <SelectDialog
            title="Restore Session"
            description="Select a session to restore:"
            options={sessionManager.getSessionOptions(appState.currentSessionId, false)}
            isLoading={sessionManager.isLoading}
            loadingMessage="Loading sessions..."
            emptyMessage="No sessions available."
            onSelect={handleSessionRestoreSelect}
            onCancel={handleDialogCancel}
            showNumbers={true}
            showDescriptions={false}
            maxItemsToShow={8}
          />
        )}

        {/* Session delete dialog */}
        {activeDialog === 'session_delete' && (
          <SelectDialog
            title="Delete Session"
            description="Select a session to delete (cannot be undone):"
            options={sessionManager.getSessionOptions(appState.currentSessionId, true)}
            isLoading={sessionManager.isLoading}
            loadingMessage="Loading sessions..."
            emptyMessage="No other sessions available to delete."
            onSelect={handleSessionDeleteSelect}
            onCancel={handleDialogCancel}
            showNumbers={true}
            showDescriptions={false}
            maxItemsToShow={8}
            borderColor={theme.status.error}
          />
        )}

        {/* Todo status indicator - above input */}
        {appState.isInputActive && !appState.pendingConfirmation && !isDialogActive && (
          <TodoStatusIndicator
            todo={appState.currentTodo}
            isStreaming={appState.isStreaming}
          />
        )}

        {/* Input area with slash command and shell command support */}
        {appState.isInputActive && !appState.pendingConfirmation && !isDialogActive && (
          <InputPrompt
            buffer={buffer}
            onSubmit={appActions.sendMessage}
            onSlashCommand={handleSlashCommand}
            onShellCommand={handleShellCommand}
            onShellModeChange={setIsShellMode}
            onShellBlocked={handleShellBlocked}
            slashCommands={commands}
            commandContext={commandContext}
            agentProfile={appState.currentProfile}
            sessionId={appState.currentSessionId || undefined}
            disabled={isShellExecuting}
            isStreaming={appState.isStreaming}
          />
        )}

        {/* Status bar - below input */}
        <Header isShellMode={isShellMode} cwd={shellCwd} />
      </Box>
    </Box>
  );
};
