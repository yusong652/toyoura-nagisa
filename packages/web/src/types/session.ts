export interface ChatSession {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface TokenUsage {
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  tokens_left?: number
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