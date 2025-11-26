/**
 * Command System Type Definitions
 * Reference: Gemini CLI ui/commands/types.ts
 */

import type { ReactNode } from 'react';
import type { HistoryItem, HistoryItemWithoutId, SessionStats } from '../types.js';

// Forward declare manager types to avoid circular dependencies
// These will be properly typed when the command system is implemented
type ConnectionManagerLike = {
  send: (message: unknown) => void;
  connectToSession: (sessionId: string) => Promise<void>;
  disconnect: () => void;
};

type SessionManagerLike = {
  createSession: (name?: string) => Promise<string>;
  loadSessions: () => Promise<unknown[]>;
  deleteSession: (sessionId: string) => Promise<void>;
};

/**
 * Context provided to all command actions
 */
export interface CommandContext {
  /** Invocation details when command is called */
  invocation?: {
    /** The raw, untrimmed input string from the user */
    raw: string;
    /** The primary name of the command that was matched */
    name: string;
    /** The arguments string that follows the command name */
    args: string;
  };

  /** Core services */
  services: {
    connectionManager: ConnectionManagerLike;
    sessionManager: SessionManagerLike;
  };

  /** UI state and methods */
  ui: {
    /** Adds a new item to the history display */
    addItem: (item: HistoryItemWithoutId, timestamp?: number) => void;
    /** Clears all history items */
    clear: () => void;
    /** Sets a pending item (for loading indicators) */
    setPendingItem: (item: HistoryItemWithoutId | null) => void;
    /** Reloads the command list */
    reloadCommands: () => void;
  };

  /** Session state */
  session: {
    currentSessionId: string | null;
    stats: SessionStats;
  };
}

/**
 * Command kinds
 */
export enum CommandKind {
  BUILT_IN = 'built-in',
  FILE = 'file',
  MCP_PROMPT = 'mcp-prompt',
}

/**
 * Return type for message action
 */
export interface MessageActionReturn {
  type: 'message';
  messageType: 'info' | 'error';
  content: string;
}

/**
 * Return type for quit action
 */
export interface QuitActionReturn {
  type: 'quit';
  messages?: HistoryItem[];
}

/**
 * Return type for dialog action
 */
export interface OpenDialogActionReturn {
  type: 'dialog';
  dialog: 'help' | 'profile' | 'memory' | 'session' | 'settings' | 'theme';
  props?: Record<string, unknown>;
}

/**
 * Return type for profile switch action
 */
export interface ProfileSwitchActionReturn {
  type: 'profile_switch';
  profile: string;
}

/**
 * Return type for memory toggle action
 */
export interface MemoryToggleActionReturn {
  type: 'memory_toggle';
  enabled: boolean;
}

/**
 * Return type for load history action
 */
export interface LoadHistoryActionReturn {
  type: 'load_history';
  history: HistoryItemWithoutId[];
}

/**
 * Return type for submit prompt action
 */
export interface SubmitPromptActionReturn {
  type: 'submit_prompt';
  content: string;
}

/**
 * Return type for custom dialog action
 */
export interface OpenCustomDialogActionReturn {
  type: 'custom_dialog';
  component: ReactNode;
}

/**
 * Union of all possible command action returns
 */
export type SlashCommandActionReturn =
  | MessageActionReturn
  | QuitActionReturn
  | OpenDialogActionReturn
  | ProfileSwitchActionReturn
  | MemoryToggleActionReturn
  | LoadHistoryActionReturn
  | SubmitPromptActionReturn
  | OpenCustomDialogActionReturn;

/**
 * Slash command definition
 */
export interface SlashCommand {
  /** Primary command name (without slash) */
  name: string;
  /** Alternative names/aliases */
  altNames?: string[];
  /** Human-readable description */
  description: string;
  /** Hide from help listing */
  hidden?: boolean;
  /** Command kind */
  kind: CommandKind;

  /**
   * Command action handler
   * @param context - Command context with services and UI methods
   * @param args - Arguments passed to the command
   * @returns void or action return type
   */
  action?: (
    context: CommandContext,
    args: string,
  ) => void | SlashCommandActionReturn | Promise<void | SlashCommandActionReturn>;

  /**
   * Tab completion provider
   * @param context - Command context
   * @param partialArg - Partial argument being typed
   * @returns Array of completion suggestions
   */
  completion?: (
    context: CommandContext,
    partialArg: string,
  ) => Promise<string[]> | string[];

  /** Sub-commands */
  subCommands?: SlashCommand[];
}
