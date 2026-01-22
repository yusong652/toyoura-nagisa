/**
 * Chat session data structure.
 *
 * Represents a single conversation session with metadata.
 */
export interface ChatSession {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
  mode?: SessionMode;
  llm_config?: {
    provider: string;
    model: string;
    secondary_model?: string;
  };
}

export type SessionMode = 'build' | 'plan';

/**
 * Token usage statistics from LLM API.
 *
 * All fields are optional to accommodate partial data from different sources.
 * - prompt_tokens: Input tokens (context window usage)
 * - completion_tokens: Output tokens (AI response)
 * - total_tokens: Total tokens used
 * - tokens_left: Remaining tokens in context window
 */
export interface TokenUsage {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  tokens_left?: number;
}

export interface SessionContextType {
  // Session state
  sessions: ChatSession[]
  currentSessionId: string | null
  sessionLoadAttempted: boolean
  sessionTokenUsage: TokenUsage | null

  // Session operations
  refreshSessions: () => Promise<ChatSession[]>
  createNewSession: (name?: string) => Promise<string>
  switchSession: (sessionId: string) => Promise<void>
  deleteSession: (sessionId: string) => Promise<void>
  refreshTitle: (sessionId: string) => Promise<void>
}
