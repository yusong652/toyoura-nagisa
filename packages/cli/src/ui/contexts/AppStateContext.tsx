/**
 * App State Context
 * Provides global app state to all components
 */

import { createContext, useContext } from 'react';
import type { HistoryItem, ToolConfirmationData, ConnectionStatus } from '../types.js';
import type { StreamingContextValue } from './StreamingContext.js';
import { StreamingState } from './StreamingContext.js';

export interface AppState {
  // Connection
  connectionStatus: ConnectionStatus;
  error: string | null;

  // Session
  currentSessionId: string | null;

  // History
  history: HistoryItem[];

  // Streaming
  streamingState: StreamingContextValue;
  isStreaming: boolean;

  // Tool confirmation
  pendingConfirmation: ToolConfirmationData | null;

  // UI state
  isQuitting: boolean;
  isInputActive: boolean;

  // Message queue (messages queued during streaming)
  messageQueue: string[];
}

export interface AppActions {
  // History
  addHistoryItem: (item: Omit<HistoryItem, 'id'>, timestamp?: number) => string;
  updateHistoryItem: (id: string, updates: Record<string, any>) => void;
  clearHistory: () => void;

  // Session
  switchSession: (sessionId: string) => Promise<void>;
  createSession: (name?: string) => Promise<string>;

  // Messages
  sendMessage: (text: string) => void;
  cancelRequest: () => void;

  // Tool confirmation
  confirmTool: (approved: boolean, message?: string) => void;

  // UI
  quit: () => void;
  clearScreen: () => void;

  // Error
  clearError: () => void;
}

const defaultState: AppState = {
  connectionStatus: 'disconnected',
  error: null,
  currentSessionId: null,
  history: [],
  streamingState: {
    state: StreamingState.Idle,
    currentMessageId: null,
    thinkingContent: null,
  },
  isStreaming: false,
  pendingConfirmation: null,
  isQuitting: false,
  isInputActive: true,
  messageQueue: [],
};

const defaultActions: AppActions = {
  addHistoryItem: () => '',
  updateHistoryItem: () => {},
  clearHistory: () => {},
  switchSession: async () => {},
  createSession: async () => '',
  sendMessage: () => {},
  cancelRequest: () => {},
  confirmTool: () => {},
  quit: () => {},
  clearScreen: () => {},
  clearError: () => {},
};

export const AppStateContext = createContext<AppState>(defaultState);
export const AppActionsContext = createContext<AppActions>(defaultActions);

export function useAppState(): AppState {
  return useContext(AppStateContext);
}

export function useAppActions(): AppActions {
  return useContext(AppActionsContext);
}
