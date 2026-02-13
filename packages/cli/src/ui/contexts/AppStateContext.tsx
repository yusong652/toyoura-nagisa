/**
 * App State Context
 * Provides global app state to all components
 *
 * Key Architecture (following Gemini CLI pattern):
 * - history: Committed items that won't change (rendered in <Static>)
 * - pendingHistoryItems: Items currently being streamed (rendered outside <Static>)
 */

import { createContext, useContext } from 'react';
import type { TokenUsage, ChatSession } from '@toyoura-nagisa/core';
import type {
  HistoryItem,
  HistoryItemWithoutId,
  ToolConfirmationData,
  ConnectionStatus,
  SessionMode,
} from '../types.js';
import type { TodoItem } from '../hooks/useTodoStatus.js';
import type { BackgroundTask, PfcTask } from '../types/streamEvents.js';
import { StreamingState } from './StreamingContext.js';

/**
 * Extended streaming state with content
 */
export interface StreamingStateData {
  state: StreamingState;
  thinkingContent: string | null;
}

export interface AppState {
  // Connection
  connectionStatus: ConnectionStatus;
  error: string | null;

  // Session
  currentSessionId: string | null;
  sessionMode: SessionMode;
  llmConfig: ChatSession['llm_config'] | null;
  contextWindow: number | null;

  // Thinking Level ("default" | "low" | "high")
  thinkingLevel: string;
  // Available thinking level options (for UI hint)
  thinkingLevelOptions: string[];

  // History (committed items - rendered in <Static>)
  history: HistoryItem[];

  // Pending history items (currently streaming - rendered outside <Static>)
  pendingHistoryItems: HistoryItemWithoutId[];

  // Streaming
  streamingState: StreamingStateData;
  isStreaming: boolean;

  // User shell execution (for Ctrl+B backgrounding)
  isShellExecuting: boolean;

  // User PFC console execution (for Ctrl+B backgrounding)
  isPfcExecuting: boolean;

  // Tool confirmation
  pendingConfirmation: ToolConfirmationData | null;

  // UI state
  isQuitting: boolean;
  isInputActive: boolean;

  // Token usage
  tokenUsage: TokenUsage | null;

  // Current todo (in_progress task)
  currentTodo: TodoItem | null;

  // Full context mode (Ctrl+O toggle - show full thinking/tool results)
  isFullContextMode: boolean;

  // Background tasks
  backgroundTasks: BackgroundTask[];
  activeBackgroundTaskCount: number;

  // PFC task (single task - PFC only supports one)
  pfcTask: PfcTask | null;

  // System Notification (Toast)
  notification: AppNotification | null;
}

export interface AppNotification {
  id: string;
  message: string;
  type: 'info' | 'success' | 'error';
}

export interface AppActions {
  // History
  addHistoryItem: (item: HistoryItemWithoutId, timestamp?: number) => string;
  updateHistoryItem: (id: string, updates: Record<string, any>) => void;
  clearHistory: () => void;

  // Session
  switchSession: (sessionId: string) => Promise<void>;
  createSession: (name?: string) => Promise<string>;
  setSessionMode: (mode: SessionMode) => void;
  cycleSessionMode: (direction: 1 | -1) => void;

  // Thinking Level
  cycleThinkingLevel: () => Promise<void>;

  // Messages
  sendMessage: (text: string, mentionedFiles?: string[]) => void;
  cancelRequest: () => void;

  // Tool confirmation
  confirmTool: (outcome: 'approve' | 'reject' | 'reject_and_tell', message?: string) => void;

  // UI
  quit: () => void;
  clearScreen: () => void;
  toggleFullContextMode: () => void;

  // Shell execution state (for Ctrl+B)
  setShellExecuting: (executing: boolean) => void;

  // PFC console execution state (for Ctrl+B)
  setPfcExecuting: (executing: boolean) => void;

  // Error
  clearError: () => void;

  // System Notification
  showNotification: (message: string, type?: 'info' | 'success' | 'error', duration?: number) => void;
  clearNotification: () => void;
}

const defaultState: AppState = {
  connectionStatus: 'disconnected',
  error: null,
  currentSessionId: null,
  sessionMode: 'build',
  llmConfig: null,
  contextWindow: null,
  thinkingLevel: 'default',
  thinkingLevelOptions: [],
  history: [],
  pendingHistoryItems: [],
  streamingState: {
    state: StreamingState.Idle,
    thinkingContent: null,
  },
  isStreaming: false,
  isShellExecuting: false,
  isPfcExecuting: false,
  pendingConfirmation: null,
  isQuitting: false,
  isInputActive: true,
  tokenUsage: null,
  currentTodo: null,
  isFullContextMode: false,
  backgroundTasks: [],
  activeBackgroundTaskCount: 0,
  pfcTask: null,
  notification: null,
};

const defaultActions: AppActions = {
  addHistoryItem: () => '',
  updateHistoryItem: () => {},
  clearHistory: () => {},
  switchSession: async () => {},
  createSession: async () => '',
  setSessionMode: () => {},
  cycleSessionMode: () => {},
  cycleThinkingLevel: async () => {},
  sendMessage: () => {},
  cancelRequest: () => {},
  confirmTool: () => {},
  quit: () => {},
  clearScreen: () => {},
  toggleFullContextMode: () => {},
  setShellExecuting: () => {},
  setPfcExecuting: () => {},
  clearError: () => {},
  showNotification: () => {},
  clearNotification: () => {},
};

export const AppStateContext = createContext<AppState>(defaultState);
export const AppActionsContext = createContext<AppActions>(defaultActions);

export function useAppState(): AppState {
  return useContext(AppStateContext);
}

export function useAppActions(): AppActions {
  return useContext(AppActionsContext);
}
