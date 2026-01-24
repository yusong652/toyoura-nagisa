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
import { Box, Static, Text } from 'ink';
import { useAppState, useAppActions } from '../contexts/AppStateContext.js';
import { HistoryItemDisplay } from '../components/messages/HistoryItemDisplay.js';
import { PendingItemDisplay } from '../components/messages/PendingItemDisplay.js';
import { InputPrompt } from '../components/InputPrompt.js';
import { Header } from '../components/Header.js';
import { AppHeader } from '../components/AppHeader.js';
import { LoadingIndicator } from '../components/LoadingIndicator.js';
import { TodoStatusIndicator } from '../components/TodoStatusIndicator.js';
import { NotificationBanner } from '../components/NotificationBanner.js';
import { ToolConfirmationPrompt } from '../components/ToolConfirmationPrompt.js';
import { SelectDialog, type SelectOption } from '../components/SelectDialog.js';
import { FullContextView } from '../components/FullContextView.js';
import { BackgroundTaskMonitor } from '../components/BackgroundTaskMonitor.js';
import { PfcTaskMonitor } from '../components/PfcTaskMonitor.js';
import { useTerminalSize } from '../hooks/useTerminalSize.js';
import { useSlashCommandProcessor } from '../hooks/useSlashCommandProcessor.js';
import { useSessionManager } from '../hooks/useSessionManager.js';
import { useShellCommand } from '../hooks/useShellCommand.js';
import { usePfcConsoleCommand } from '../hooks/usePfcConsoleCommand.js';
import { useTheme } from '../hooks/useTheme.js';
import { useTextBuffer } from '../utils/text-buffer.js';
import { MessageType } from '../types.js';
import { colors, theme, themeManager } from '../colors.js';
import { themes, type ThemeName } from '../themes/index.js';
import { apiClient } from '@toyoura-nagisa/core';

// Memoized components for performance
const MemoizedHistoryItemDisplay = memo(HistoryItemDisplay);
const MemoizedAppHeader = memo(AppHeader);

// Dialog types
type ActiveDialog =
  | 'help'
  | 'help_detail'
  | 'memory'
  | 'session'
  | 'session_restore'
  | 'session_delete'
  | 'theme'
  | 'pfc_reset'
  | 'pfc_reset_confirm'
  | 'pfc_tasks'
  | 'pfc_task_details'
  | 'models_provider'
  | 'models_primary'
  | 'models_secondary'
  | null;

// Session action type
type SessionAction = 'create' | 'restore' | 'delete';

interface LlmModelInfo {
  id: string;
  name: string;
  description?: string | null;
  context_window?: number | null;
}

interface LlmProviderInfo {
  provider: string;
  name: string;
  description?: string | null;
  models: LlmModelInfo[];
  api_key_configured: boolean;
}

interface SessionLlmConfig {
  provider: string;
  model: string;
  secondary_model?: string | null;
}

// Memory options for SelectDialog
const MEMORY_OPTIONS: SelectOption<boolean>[] = [
  { key: 'on', value: true, label: 'On', description: 'AI can recall previous conversations' },
  { key: 'off', value: false, label: 'Off', description: 'No long-term memory' },
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

// PFC reset confirmation options
const PFC_RESET_OPTIONS: SelectOption<boolean>[] = [
  { key: 'cancel', value: false, label: 'Cancel', description: 'Abort reset operation' },
  { key: 'confirm', value: true, label: 'Confirm Reset', description: 'Delete all PFC history (cannot be undone)' },
];

function formatContextWindow(value?: number | null): string | null {
  if (!value) {
    return null;
  }

  if (value >= 1_000_000) {
    return `${Math.round(value / 1_000_000)}m`;
  }

  if (value >= 1_000) {
    return `${Math.round(value / 1_000)}k`;
  }

  return String(value);
}

export const MainLayout: React.FC = () => {
  const appState = useAppState();
  const appActions = useAppActions();
  const { columns: terminalWidth } = useTerminalSize();
  const { themeName } = useTheme();

  // Track previous width to detect actual changes
  const previousWidthRef = useRef(terminalWidth);
  const resizeTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Key to force re-render of history on terminal resize
  const [renderKey, setRenderKey] = useState(0);

  // Active dialog state
  const [activeDialog, setActiveDialog] = useState<ActiveDialog>(null);
  const [selectedHelpCommand, setSelectedHelpCommand] = useState<string | null>(null);
  const [themePreviewBase, setThemePreviewBase] = useState<ThemeName | null>(null);

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
    appState.currentSessionId
  );

  // PFC console command execution
  const { executeCode: executePfcCode, isExecuting: isPfcExecuting } = usePfcConsoleCommand(
    appState.currentSessionId
  );

  // Sync shell execution state to AppState for Ctrl+B handling
  useEffect(() => {
    appActions.setShellExecuting(isShellExecuting);
  }, [isShellExecuting, appActions]);

  // Sync PFC console execution state to AppState for Ctrl+B handling
  useEffect(() => {
    appActions.setPfcExecuting(isPfcExecuting);
  }, [isPfcExecuting, appActions]);

  // Shell mode state (for UI indicator)
  const [isShellMode, setIsShellMode] = useState(false);

  // PFC console mode state (for UI indicator)
  const [isPfcConsoleMode, setIsPfcConsoleMode] = useState(false);

  useEffect(() => {
    if (activeDialog === 'theme') {
      setThemePreviewBase(themeManager.getCurrentThemeName());
      return;
    }
    setThemePreviewBase(null);
  }, [activeDialog]);

  // PFC tasks state
  const [pfcTasks, setPfcTasks] = useState<Array<{
    task_id: string;
    status: string;
    entry_script: string;
    description: string;
    start_time: number | null;
    elapsed_time: number | null;
  }>>([]);
  const [isPfcTasksLoading, setIsPfcTasksLoading] = useState(false);
  const [selectedTaskDetails, setSelectedTaskDetails] = useState<string | null>(null);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [isTaskDetailsLoading, setIsTaskDetailsLoading] = useState(false);
  const [pfcConnectionError, setPfcConnectionError] = useState<string | null>(null);

  // LLM model selection state
  const [llmProviders, setLlmProviders] = useState<LlmProviderInfo[]>([]);
  const [isLlmProvidersLoading, setIsLlmProvidersLoading] = useState(false);
  const [llmProvidersError, setLlmProvidersError] = useState<string | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(null);
  const [selectedPrimaryModelId, setSelectedPrimaryModelId] = useState<string | null>(null);
  const [currentLlmConfig, setCurrentLlmConfig] = useState<SessionLlmConfig | null>(null);

  const loadLlmProviders = useCallback(async (sessionId: string) => {
    setIsLlmProvidersLoading(true);
    setLlmProvidersError(null);
    try {
      const providersResponse = await apiClient.get<{ providers: LlmProviderInfo[] }>(
        '/api/llm-config/providers'
      );
      const providers = providersResponse.providers ?? [];
      setLlmProviders(providers);

      const sessionConfig = await apiClient.get<SessionLlmConfig | null>(
        `/api/llm-config?session_id=${sessionId}`
      );
      setCurrentLlmConfig(sessionConfig);
      setSelectedProviderId(sessionConfig?.provider ?? null);
      setSelectedPrimaryModelId(sessionConfig?.model ?? null);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load LLM models';
      setLlmProvidersError(message);
      setLlmProviders([]);
    } finally {
      setIsLlmProvidersLoading(false);
    }
  }, []);

  const activeProviderId = selectedProviderId ?? currentLlmConfig?.provider ?? null;

  const activeProvider = useMemo(() => {
    if (!activeProviderId) {
      return null;
    }
    return llmProviders.find((provider) => provider.provider === activeProviderId) ?? null;
  }, [llmProviders, activeProviderId]);

  const providerOptions = useMemo<SelectOption<string>[]>(() => {
    return llmProviders.map((provider) => {
      const descriptionParts = [];
      if (provider.description) {
        descriptionParts.push(provider.description);
      }
      if (!provider.api_key_configured) {
        descriptionParts.push('API key not configured');
      }
      return {
        key: provider.provider,
        value: provider.provider,
        label: provider.name,
        description: descriptionParts.join(' | '),
        disabled: !provider.api_key_configured,
      };
    });
  }, [llmProviders]);

  const primaryModelOptions = useMemo<SelectOption<string>[]>(() => {
    if (!activeProvider) {
      return [];
    }

    return activeProvider.models.map((model) => {
      const descriptionParts = [];
      if (model.description) {
        descriptionParts.push(model.description);
      }
      const contextWindow = formatContextWindow(model.context_window ?? undefined);
      if (contextWindow) {
        descriptionParts.push(`context ${contextWindow}`);
      }
      if (model.id !== model.name) {
        descriptionParts.push(model.id);
      }
      return {
        key: model.id,
        value: model.id,
        label: model.name,
        description: descriptionParts.join(' | '),
      };
    });
  }, [activeProvider]);

  const currentPrimaryModelId = selectedPrimaryModelId
    ?? (currentLlmConfig?.provider === activeProviderId ? currentLlmConfig.model : null);

  const currentSecondaryModelId = currentLlmConfig?.provider === activeProviderId
    ? (currentLlmConfig.secondary_model ?? currentPrimaryModelId)
    : currentPrimaryModelId;

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

  const helpOptions = useMemo<SelectOption<string>[]>(() => {
    return commands
      .filter((cmd) => !cmd.hidden && cmd.name !== 'help')
      .map((cmd) => ({
        key: cmd.name,
        value: cmd.name,
        label: `/${cmd.name}`,
        description: cmd.description,
      }));
  }, [commands]);

  useEffect(() => {
    if (activeDialog !== 'models_provider') {
      return;
    }

    if (!appState.currentSessionId) {
      setLlmProvidersError('No active session. Create or restore a session first.');
      setIsLlmProvidersLoading(false);
      return;
    }

    setSelectedProviderId(null);
    setSelectedPrimaryModelId(null);
    void loadLlmProviders(appState.currentSessionId);
  }, [activeDialog, appState.currentSessionId, loadLlmProviders]);

  // Track session ID to detect session changes
  const previousSessionIdRef = useRef(appState.currentSessionId);

  // Force re-render when session changes (Static doesn't clear previous output)
  useEffect(() => {
    if (previousSessionIdRef.current !== appState.currentSessionId) {
      previousSessionIdRef.current = appState.currentSessionId;
      setRenderKey((prev) => prev + 1);
    }
  }, [appState.currentSessionId]);

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

  // Refresh Static output when theme changes
  useEffect(() => {
    setRenderKey((prev) => prev + 1);
  }, [themeName]);

  // Update text buffer viewport width when terminal size changes
  useEffect(() => {
    buffer.setViewportWidth(inputWidth);
  }, [inputWidth, buffer]);

  // Handle help command selection
  const handleHelpSelect = useCallback((cmdName: string) => {
    setSelectedHelpCommand(cmdName);
    setActiveDialog('help_detail');
  }, []);

  // Handle memory selection from dialog
  const handleMemorySelect = useCallback((enabled: boolean) => {
    appActions.setMemoryEnabled(enabled);
    appActions.showNotification(
      `Memory ${enabled ? 'enabled' : 'disabled'}`,
      'info'
    );
    setActiveDialog(null);
  }, []);

  // Handle theme selection from dialog
  const handleThemeSelect = useCallback((themeName: ThemeName) => {
    themeManager.setTheme(themeName);
    setThemePreviewBase(null);
    setActiveDialog(null);
    // In alternate buffer mode, Ink handles re-rendering automatically
  }, [appActions]);

  const handleThemeHighlight = useCallback((themeName: ThemeName) => {
    themeManager.setTheme(themeName, false);
  }, []);

  // Handle dialog cancel
  const handleDialogCancel = useCallback(() => {
    if (activeDialog === 'theme' && themePreviewBase) {
      themeManager.setTheme(themePreviewBase);
    }
    setThemePreviewBase(null);
    setActiveDialog(null);
  }, [activeDialog, themePreviewBase]);

  // Handle session action selection (create/restore/delete)
  const handleSessionActionSelect = useCallback(async (action: SessionAction) => {
    switch (action) {
      case 'create': {
        try {
          const sessionId = await appActions.createSession();
          appActions.showNotification(
            `Created new session: ${sessionId.slice(0, 8)}...`,
            'success'
          );
        } catch (e) {
          appActions.showNotification(
            e instanceof Error ? e.message : 'Failed to create session',
            'error'
          );
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
    } catch (e) {
      appActions.showNotification(
        e instanceof Error ? e.message : 'Failed to restore session',
        'error'
      );
    }
    setActiveDialog(null);
  }, [sessionManager, appActions, appState.currentSessionId]);

  // Handle session delete selection
  const handleSessionDeleteSelect = useCallback(async (sessionId: string) => {
    const session = sessionManager.sessions.find(s => s.id === sessionId);
    const success = await sessionManager.deleteSession(sessionId);
    if (success) {
      appActions.showNotification(
        `Deleted session: ${session?.name || sessionId}`,
        'success'
      );
    } else {
      appActions.showNotification(
        sessionManager.error || 'Failed to delete session',
        'error'
      );
    }
    setActiveDialog(null);
  }, [sessionManager, appActions]);

  const resolvePrimaryModelId = useCallback((providerId: string): string | null => {
    const provider = llmProviders.find((item) => item.provider === providerId);
    if (!provider || provider.models.length === 0) {
      return null;
    }

    if (currentLlmConfig?.provider === providerId && currentLlmConfig.model) {
      return currentLlmConfig.model;
    }

    return provider.models[0]?.id ?? null;
  }, [llmProviders, currentLlmConfig]);

  const handleModelsProviderSelect = useCallback((providerId: string) => {
    setSelectedProviderId(providerId);
    setSelectedPrimaryModelId(resolvePrimaryModelId(providerId));
    setActiveDialog('models_primary');
  }, [resolvePrimaryModelId]);

  const handleModelsPrimarySelect = useCallback((modelId: string) => {
    setSelectedPrimaryModelId(modelId);
    setActiveDialog('models_secondary');
  }, []);

  const handleModelsSecondarySelect = useCallback(async (secondaryModelId: string) => {
      if (!appState.currentSessionId) {
        appActions.showNotification(
          'No active session. Create or restore a session first.',
          'error'
        );
        setActiveDialog(null);
        return;
      }

      if (!selectedProviderId || !selectedPrimaryModelId) {
        appActions.showNotification(
          'Please select a provider and primary model first.',
          'error'
        );
        setActiveDialog(null);
        return;
      }

    try {
      await apiClient.post(`/api/llm-config?session_id=${appState.currentSessionId}`, {
        provider: selectedProviderId,
        model: selectedPrimaryModelId,
        secondary_model: secondaryModelId,
      });

      const updatedConfig: SessionLlmConfig = {
        provider: selectedProviderId,
        model: selectedPrimaryModelId,
        secondary_model: secondaryModelId,
      };
      setCurrentLlmConfig(updatedConfig);

      appActions.showNotification(
        `Session LLM updated: ${selectedProviderId}/${selectedPrimaryModelId}`,
        'success'
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update session LLM config';
      appActions.showNotification(message, 'error');
    }

    setActiveDialog(null);
  }, [
    appActions,
    appState.currentSessionId,
    selectedProviderId,
    selectedPrimaryModelId,
  ]);

  const handleModelsPrimaryCancel = useCallback(() => {
    setActiveDialog('models_provider');
  }, []);

  const handleModelsSecondaryCancel = useCallback(() => {
    setActiveDialog('models_primary');
  }, []);

  // Handle PFC reset confirmation
  const handlePfcResetConfirm = useCallback(async (confirmed: boolean) => {
    if (!confirmed) {
      appActions.showNotification('PFC workspace reset cancelled', 'info');
      setActiveDialog(null);
      return;
    }

    // Execute reset
    try {
      appActions.showNotification('Resetting PFC workspace...', 'info');

      /** Response data from reset (unwrapped from ApiResponse) */
      interface PfcResetData {
        user_console?: { success: boolean; deleted_scripts: number };
        tasks?: { success: boolean; cleared_count: number };
        git?: { success: boolean; deleted_commits: number };
        connected: boolean;
      }

      const response = await apiClient.post<PfcResetData>('/api/pfc/console/reset', {
        session_id: appState.currentSessionId || 'unknown',
      });

      const parts: string[] = [];
      if (response.user_console?.deleted_scripts) {
        parts.push(`${response.user_console.deleted_scripts} scripts`);
      }
      if (response.tasks?.cleared_count) {
        parts.push(`${response.tasks.cleared_count} tasks`);
      }
      if (response.git?.deleted_commits) {
        parts.push(`${response.git.deleted_commits} git snapshots`);
      }

      const summary = parts.length > 0 ? ` (cleared: ${parts.join(', ')})` : '';
      appActions.showNotification(
        `PFC workspace reset complete${summary}`,
        'success'
      );
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'PFC reset failed';
      appActions.showNotification(errorMessage, 'error');
    }

    setActiveDialog(null);
  }, [appActions, appState.currentSessionId]);

  // Load PFC tasks when dialog opens
  const loadPfcTasks = useCallback(async () => {
    setIsPfcTasksLoading(true);
    setPfcConnectionError(null);
    try {
      /** Response data from tasks list (unwrapped from ApiResponse) */
      interface TasksListData {
        tasks: Array<{
          task_id: string;
          status: string;
          entry_script: string;
          description: string;
          start_time: number | null;
          elapsed_time: number | null;
        }>;
        total_count: number;
        displayed_count: number;
        has_more: boolean;
        connected: boolean;
      }
      const response = await apiClient.get<TasksListData>('/api/pfc/console/tasks?limit=20&offset=0');
      
      if (!response.connected) {
        setPfcConnectionError('PFC Server is not connected.');
        setPfcTasks([]);
      } else {
        setPfcTasks(response.tasks);
      }
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load PFC tasks';
      // Do not close dialog, show error state instead
      setPfcConnectionError(errorMessage);
      setPfcTasks([]);
    } finally {
      setIsPfcTasksLoading(false);
    }
  }, []);

  // Handle PFC task selection - fetch details and display
  const handlePfcTaskSelect = useCallback(async (taskId: string) => {
    if (taskId === 'retry') {
      void loadPfcTasks();
      return;
    }

    setSelectedTaskId(taskId);
    setIsTaskDetailsLoading(true);
    setActiveDialog('pfc_task_details');

    try {
      /** Response data from task status (unwrapped from ApiResponse) */
      interface TaskStatusData {
        task_id: string;
        status: string;
        entry_script: string | null;
        description: string | null;
        output: string | null;
        result: unknown;
        start_time: number | null;
        end_time: number | null;
        elapsed_time: number | null;
        git_commit: string | null;
        error: string | null;
        connected: boolean;
      }

      // Include session_id for LLM intent awareness
      const sessionParam = appState.currentSessionId ? `?session_id=${appState.currentSessionId}` : '';
      const response = await apiClient.get<TaskStatusData>(`/api/pfc/console/tasks/${taskId}${sessionParam}`);

      // Format timestamp
      const formatTime = (ts: number | null) => {
        if (!ts) return 'n/a';
        const dt = new Date(ts * 1000);
        return dt.toLocaleString();
      };

      // Build output message
      const lines: string[] = [
        `Status: ${response.status}`,
        `Script: ${response.entry_script || 'n/a'}`,
        `Description: ${response.description || 'n/a'}`,
        `Started: ${formatTime(response.start_time)}`,
        `Ended: ${formatTime(response.end_time)}`,
        `Elapsed: ${response.elapsed_time ? `${response.elapsed_time.toFixed(1)}s` : 'n/a'}`,
        `Git: ${response.git_commit ? response.git_commit.slice(0, 8) : 'n/a'}`,
      ];

      // Add error for failed tasks
      if (response.status === 'failed' && response.error) {
        lines.push('', '--- Error ---', response.error);
      }

      const output = response.output || '(no output)';
      const truncatedOutput = output.length > 500 ? output.slice(0, 500) + '... (truncated)' : output;
      lines.push('', '--- Output ---', truncatedOutput);

      setSelectedTaskDetails(lines.join('\n'));
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch task details';
      setSelectedTaskDetails(`Error: ${errorMessage}`);
    } finally {
      setIsTaskDetailsLoading(false);
    }
  }, [appState.currentSessionId]);

  // Handle PFC task details actions
  const handlePfcTaskDetailAction = useCallback((action: string) => {
    if (action === 'back') {
      setActiveDialog('pfc_tasks');
      loadPfcTasks();
    } else if (action === 'chat') {
      if (selectedTaskDetails) {
        // Just add to history for user reference
        // Backend UserPfcTaskMonitor already captured the context via the API call
        appActions.addHistoryItem({
          type: MessageType.INFO,
          message: `Task ${selectedTaskId} Details:\n\n${selectedTaskDetails}`,
        });
      }
      setActiveDialog(null);
    } else {
      setActiveDialog(null);
    }
  }, [selectedTaskDetails, selectedTaskId, loadPfcTasks, appActions]);

  // Build PFC task options for SelectDialog (single-line format)
  const pfcTaskOptions = useMemo(() => {
    if (pfcConnectionError) {
      return [{
        key: 'retry',
        value: 'retry',
        label: 'Connection Failed (Retry)',
        description: 'PFC Server is not reachable. Ensure it is running in PFC GUI and try again.',
      }];
    }

    const statusEmoji: Record<string, string> = {
      running: '...',
      completed: 'OK',
      failed: 'X',
      interrupted: '!',
    };

    return pfcTasks.map((task) => {
      const emoji = statusEmoji[task.status] || '?';
      const elapsed = task.elapsed_time ? `${task.elapsed_time.toFixed(1)}s` : '---';
      const desc = task.description || task.entry_script || '';
      // Single-line format: [status] id | elapsed | description
      return {
        key: task.task_id,
        value: task.task_id,
        label: `[${emoji}] ${task.task_id} | ${elapsed} | ${desc}`,
      };
    });
  }, [pfcTasks, pfcConnectionError]);

  // Handle shell command blocked during streaming
  const handleShellBlocked = useCallback(() => {
    appActions.showNotification(
      'Shell commands are disabled while AI is responding. Please wait.',
      'error'
    );
  }, [appActions]);

  // Handle PFC console command blocked during streaming
  const handlePfcConsoleBlocked = useCallback(() => {
    appActions.showNotification(
      'PFC console commands are disabled while AI is responding. Please wait.',
      'error'
    );
  }, [appActions]);

  // Handle PFC console command execution (> prefix)
  const handlePfcConsoleCommand = useCallback(async (code: string) => {
    // Add user's PFC Python command to history with distinct styling
    appActions.addHistoryItem({
      type: MessageType.PFC_CONSOLE_COMMAND,
      code: code,
    });

    // Execute the PFC Python code
    const result = await executePfcCode(code);

    if (result) {
      // Add PFC result with distinct styling
      // isError is true when disconnected OR when execution failed with error
      const hasError = !result.connected || (result.error != null && result.error !== '');
      appActions.addHistoryItem({
        type: MessageType.PFC_CONSOLE_RESULT,
        taskId: result.task_id,
        scriptName: result.script_name,
        output: result.output,
        result: result.result,
        elapsedTime: result.elapsed_time,
        isError: hasError,
        error: result.error,
        connected: result.connected,
      });
    } else {
      appActions.addHistoryItem({
        type: MessageType.ERROR,
        message: 'Failed to execute PFC Python command',
      });
    }
  }, [appActions, executePfcCode]);

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
      // isError is determined by non-zero exit code
      appActions.addHistoryItem({
        type: MessageType.SHELL_RESULT,
        stdout: result.stdout || '',
        stderr: result.stderr || '',
        exitCode: result.exit_code,
        isError: result.exit_code !== 0,
        backgrounded: result.backgrounded,
        processId: result.process_id,
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
        appActions.showNotification(
          `Memory ${result.enabled ? 'enabled' : 'disabled'}`,
          'info'
        );
        break;

      case 'quit':
        appActions.quit();
        break;

      case 'dialog':
        // Open the appropriate dialog
        if (result.dialog === 'help') {
          setActiveDialog('help');
        } else if (result.dialog === 'memory') {
          setActiveDialog('memory');
        } else if (result.dialog === 'session') {
          setActiveDialog('session');
        } else if (result.dialog === 'theme') {
          setActiveDialog('theme');
        } else if (result.dialog === 'pfc_reset') {
          setActiveDialog('pfc_reset_confirm');
        } else if (result.dialog === 'pfc_tasks') {
          setActiveDialog('pfc_tasks');
          loadPfcTasks();
        } else if (result.dialog === 'models_provider') {
          setActiveDialog('models_provider');
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
        {/* Shell executing indicator */}
        {isShellExecuting && (
          <Box flexDirection="row" marginBottom={1}>
            <Text color={colors.primary}>{'  ⎿  '}</Text>
            <Text color={theme.text.muted} dimColor>Running... (Ctrl+B to background)</Text>
          </Box>
        )}
        {/* PFC console executing indicator */}
        {isPfcExecuting && (
          <Box flexDirection="row" marginBottom={1}>
            <Text color={colors.primary}>{'  ⎿  '}</Text>
            <Text color={theme.text.muted} dimColor>PFC executing... (Ctrl+B to background)</Text>
          </Box>
        )}
      </Box>
    ),
    [appState.pendingHistoryItems, appState.isStreaming, appState.streamingState.thinkingContent, isShellExecuting, isPfcExecuting],
  );

  // Always render Static to prevent unmount/remount issues
  // Full context mode renders FullContextView AFTER Static (which only shows new items)
  return (
    <Box flexDirection="column" width="100%">
      {/* Welcome header - rendered outside Static to avoid removal issues */}
      {/* Ink's Static doesn't clear previous output when items are removed */}
      {!appState.isFullContextMode && showWelcomeHeader && <MemoizedAppHeader showTips={true} />}

      {/* Static content area - ALWAYS mounted to preserve internal state */}
      {/* Key changes on resize to force re-render and fix layout artifacts */}
      <Static key={renderKey} items={staticItems}>
        {(item) => item}
      </Static>

      {/* Full context view mode - shows after Static to avoid remount */}
      {appState.isFullContextMode ? (
        <FullContextView onClose={appActions.toggleFullContextMode} />
      ) : (
        <>
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

        {/* Help dialog */}
        {activeDialog === 'help' && (
          <SelectDialog
            title="Nagisa CLI Help"
            description="Select a command to populate the input:"
            options={helpOptions}
            onSelect={handleHelpSelect}
            onCancel={handleDialogCancel}
            showNumbers={false}
            showDescriptions={true}
            maxItemsToShow={12}
          />
        )}

        {/* Help detail dialog */}
        {activeDialog === 'help_detail' && selectedHelpCommand && (
          <SelectDialog
            title={`Help: /${selectedHelpCommand}`}
            description={(() => {
              const cmd = commands.find(c => c.name === selectedHelpCommand);
              if (!cmd) return 'Command not found.';
              
              const parts = [cmd.description];
              if (cmd.usage) {
                parts.push('', 'Usage:', cmd.usage);
              }
              if (cmd.altNames?.length) {
                parts.push('', `Aliases: ${cmd.altNames.map(a => '/' + a).join(', ')}`);
              }
              if (cmd.subCommands?.length) {
                parts.push('', `Subcommands: ${cmd.subCommands.map(s => s.name).join(', ')}`);
              }
              return parts.join('\n');
            })()}
            options={[
              { key: 'back', value: 'back', label: 'Back', description: 'Return to command list' },
              { key: 'close', value: 'close', label: 'Close', description: 'Exit help' },
            ]}
            onSelect={(value) => {
              if (value === 'back') {
                setActiveDialog('help');
              } else {
                setActiveDialog(null);
              }
            }}
            onCancel={() => setActiveDialog('help')}
            showNumbers={false}
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
            showDescriptions={true}
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
            onHighlight={handleThemeHighlight}
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

        {/* LLM provider selection dialog */}
        {activeDialog === 'models_provider' && (
          <SelectDialog
            title="Select LLM Provider"
            description="Choose a provider for this session:"
            options={providerOptions}
            currentValue={activeProviderId ?? undefined}
            onSelect={handleModelsProviderSelect}
            onCancel={handleDialogCancel}
            isLoading={isLlmProvidersLoading}
            loadingMessage="Loading providers..."
            emptyMessage={llmProvidersError || 'No providers available.'}
            showNumbers={true}
            showDescriptions={true}
            maxItemsToShow={8}
          />
        )}

        {/* Primary model selection dialog */}
        {activeDialog === 'models_primary' && (
          <SelectDialog
            title="Select Primary Model"
            description={`Provider: ${activeProvider?.name || activeProviderId || 'Unknown'}`}
            options={primaryModelOptions}
            currentValue={currentPrimaryModelId ?? undefined}
            onSelect={handleModelsPrimarySelect}
            onCancel={handleModelsPrimaryCancel}
            emptyMessage="No models available for this provider."
            showNumbers={true}
            showDescriptions={true}
            maxItemsToShow={10}
          />
        )}

        {/* Secondary model selection dialog */}
        {activeDialog === 'models_secondary' && (
          <SelectDialog
            title="Select Secondary Model"
            description="Choose a model for SubAgents (defaults to primary if unsure):"
            options={primaryModelOptions}
            currentValue={currentSecondaryModelId ?? undefined}
            onSelect={handleModelsSecondarySelect}
            onCancel={handleModelsSecondaryCancel}
            emptyMessage="No models available for this provider."
            showNumbers={true}
            showDescriptions={true}
            maxItemsToShow={10}
          />
        )}

        {/* PFC reset confirmation dialog */}
        {activeDialog === 'pfc_reset_confirm' && (
          <SelectDialog
            title="Reset PFC Workspace"
            description="This will permanently delete:\n  - Quick console scripts\n  - All task history\n  - Git pfc-executions branch\n\nAre you sure?"
            options={PFC_RESET_OPTIONS}
            onSelect={handlePfcResetConfirm}
            onCancel={handleDialogCancel}
            borderColor={theme.status.error}
          />
        )}

        {/* PFC tasks list dialog - hidden when tool confirmation is active */}
        {activeDialog === 'pfc_tasks' && !appState.pendingConfirmation && (
          <SelectDialog
            title="PFC Tasks"
            description={pfcConnectionError ? `Error: ${pfcConnectionError}` : "Select a task to view details:"}
            options={pfcTaskOptions}
            isLoading={isPfcTasksLoading}
            loadingMessage="Loading tasks..."
            emptyMessage="No PFC tasks found."
            onSelect={handlePfcTaskSelect}
            onCancel={handleDialogCancel}
            showNumbers={false}
            showDescriptions={false}
            maxItemsToShow={10}
          />
        )}

        {/* PFC task details dialog */}
        {activeDialog === 'pfc_task_details' && (
          <SelectDialog
            title={`Task: ${selectedTaskId}`}
            description={selectedTaskDetails || ''}
            options={[
              { key: 'back', value: 'back', label: 'Back', description: 'Return to task list' },
              { key: 'chat', value: 'chat', label: 'Post to Chat', description: 'Add details to history' },
              { key: 'close', value: 'close', label: 'Close', description: 'Exit dialog' },
            ]}
            isLoading={isTaskDetailsLoading}
            loadingMessage="Loading task details..."
            onSelect={handlePfcTaskDetailAction}
            onCancel={() => {
              setActiveDialog('pfc_tasks');
              loadPfcTasks();
            }}
            showNumbers={false}
          />
        )}

        {/* Background task monitor - above todo status */}
        {appState.isInputActive && !appState.pendingConfirmation && !isDialogActive && (
          <BackgroundTaskMonitor
            activeTasks={appState.backgroundTasks}
            activeCount={appState.activeBackgroundTaskCount}
          />
        )}

        {/* PFC task monitor - above todo status */}
        {appState.isInputActive && !appState.pendingConfirmation && !isDialogActive && (
          <PfcTaskMonitor currentTask={appState.pfcTask} />
        )}

        {/* Spacer between task monitors and todo indicator */}
        {appState.isInputActive && !appState.pendingConfirmation && !isDialogActive &&
          (appState.activeBackgroundTaskCount > 0 || (appState.pfcTask && appState.pfcTask.status === 'running')) && (
          <Box height={1} />
        )}

        {/* Todo status indicator - above input */}
        {appState.isInputActive && !appState.pendingConfirmation && !isDialogActive && (
          <Box flexDirection="column">
            <TodoStatusIndicator
              todo={appState.currentTodo}
              isStreaming={appState.isStreaming}
            />
            {/* System Notification Banner - renders only when active */}
            <NotificationBanner />
          </Box>
        )}

        {/* Input area with slash command, shell command and PFC console support */}
        {appState.isInputActive && !appState.pendingConfirmation && !isDialogActive && (
          <InputPrompt
            buffer={buffer}
            onSubmit={appActions.sendMessage}
            onSlashCommand={handleSlashCommand}
            onShellCommand={handleShellCommand}
            onShellModeChange={setIsShellMode}
            onShellBlocked={handleShellBlocked}
            onPfcConsoleCommand={handlePfcConsoleCommand}
            onPfcConsoleModeChange={setIsPfcConsoleMode}
            onPfcConsoleBlocked={handlePfcConsoleBlocked}
            onModeCycle={appActions.cycleSessionMode}
            sessionMode={appState.sessionMode}
            terminalWidth={terminalWidth}
            slashCommands={commands}
            commandContext={commandContext}
            sessionId={appState.currentSessionId || undefined}
            disabled={isShellExecuting || isPfcExecuting}
            isStreaming={appState.isStreaming}
          />
        )}

            {/* Status bar - below input */}
            <Header isShellMode={isShellMode} isShellExecuting={isShellExecuting} isPfcConsoleMode={isPfcConsoleMode} cwd={shellCwd} />
          </Box>
        </>
      )}
    </Box>
  );
};
