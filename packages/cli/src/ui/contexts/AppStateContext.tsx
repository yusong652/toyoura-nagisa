/**
 * App State Context
 * Provides global app state to all components
 *
 * Key Architecture (following Gemini CLI pattern):
 * - history: Committed items that won't change (rendered in <Static>)
 * - pendingHistoryItems: Items currently being streamed (rendered outside <Static>)
 */

import { createContext, useContext } from 'react';
import type { HistoryItem, HistoryItemWithoutId, ToolConfirmationData, ConnectionStatus, AgentProfileType, AgentProfileInfo } from '../types.js';
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

  // Agent profile
  currentProfile: AgentProfileType;
  availableProfiles: AgentProfileInfo[];
  isProfileLoading: boolean;

  // Memory
  memoryEnabled: boolean;

  // History (committed items - rendered in <Static>)
  history: HistoryItem[];

  // Pending history items (currently streaming - rendered outside <Static>)
  pendingHistoryItems: HistoryItemWithoutId[];

  // Streaming
  streamingState: StreamingStateData;
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
  addHistoryItem: (item: HistoryItemWithoutId, timestamp?: number) => string;
  updateHistoryItem: (id: string, updates: Record<string, any>) => void;
  clearHistory: () => void;

  // Session
  switchSession: (sessionId: string) => Promise<void>;
  createSession: (name?: string) => Promise<string>;

  // Agent profile
  setProfile: (profile: AgentProfileType) => void;
  refreshProfiles: () => Promise<void>;

  // Memory
  setMemoryEnabled: (enabled: boolean) => void;

  // Messages
  sendMessage: (text: string, mentionedFiles?: string[]) => void;
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
  currentProfile: 'pfc',
  availableProfiles: [],
  isProfileLoading: false,
  memoryEnabled: false,
  history: [],
  pendingHistoryItems: [],
  streamingState: {
    state: StreamingState.Idle,
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
  setProfile: () => {},
  refreshProfiles: async () => {},
  setMemoryEnabled: () => {},
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
