/**
 * SessionManager - Platform-agnostic session lifecycle management
 *
 * Manages chat session lifecycle (CRUD operations), current session tracking,
 * and token usage monitoring. Provides event-based architecture for loose coupling
 * with platform-specific UI layers.
 *
 * Features:
 * - Session CRUD operations (create, read, update, delete)
 * - Current session tracking and persistence
 * - Token usage monitoring
 * - Event-driven updates for UI synchronization
 * - Storage abstraction for platform independence
 */

import { EventEmitter } from '../utils/EventEmitter.js'
import { SessionService } from '../services/SessionService.js'
import { ChatSession, TokenUsage } from '../types/session.js'

/**
 * Storage adapter interface for platform-independent storage
 *
 * Allows different storage implementations (localStorage, filesystem, etc.)
 */
export interface StorageAdapter {
  /**
   * Get a value from storage
   *
   * @param key - Storage key
   * @returns Promise resolving to stored value or null
   */
  get(key: string): Promise<string | null>

  /**
   * Set a value in storage
   *
   * @param key - Storage key
   * @param value - Value to store
   */
  set(key: string, value: string): Promise<void>

  /**
   * Remove a value from storage
   *
   * @param key - Storage key
   */
  remove(key: string): Promise<void>

  /**
   * Clear all stored values
   */
  clear(): Promise<void>
}

/**
 * Event types emitted by SessionManager
 */
export enum SessionEvent {
  SESSION_CREATED = 'sessionCreated',
  SESSION_SWITCHED = 'sessionSwitched',
  SESSION_DELETED = 'sessionDeleted',
  CURRENT_SESSION_DELETED = 'currentSessionDeleted',
  SESSIONS_LOADED = 'sessionsLoaded',
  TITLE_UPDATED = 'titleUpdated',
  TOKEN_USAGE_UPDATED = 'tokenUsageUpdated'
}

/**
 * Event payload types
 */
export interface SessionCreatedPayload {
  sessionId: string
  session: ChatSession
}

export interface SessionSwitchedPayload {
  sessionId: string
  previousSessionId: string | null
}

export interface SessionDeletedPayload {
  sessionId: string
}

export interface SessionsLoadedPayload {
  sessions: ChatSession[]
}

export interface TitleUpdatedPayload {
  sessionId: string
  title: string
}

export interface TokenUsageUpdatedPayload {
  sessionId: string
  usage: TokenUsage
}

/**
 * SessionManager - Core session lifecycle management
 *
 * Provides platform-agnostic session management with event-based notifications.
 * Delegates API calls to SessionService and emits events for UI updates.
 */
export class SessionManager extends EventEmitter {
  private sessionService: SessionService
  private storage: StorageAdapter
  private defaultWorkspaceRoot?: string
  private currentSessionId: string | null = null
  private sessions: ChatSession[] = []
  private tokenUsage: Map<string, TokenUsage> = new Map()

  /**
   * Create a new SessionManager
   *
   * @param sessionService - Session API service
   * @param storage - Storage adapter for persistence
   * @param defaultWorkspaceRoot - Default workspace root for newly created sessions
   */
  constructor(
    sessionService: SessionService,
    storage: StorageAdapter,
    defaultWorkspaceRoot?: string,
  ) {
    super()
    this.sessionService = sessionService
    this.storage = storage
    this.defaultWorkspaceRoot = defaultWorkspaceRoot
  }

  /**
   * Initialize session manager
   *
   * Loads current session ID from storage and loads session list.
   * Should be called once during application initialization.
   */
  async initialize(): Promise<void> {
    // Load current session ID from storage
    const storedSessionId = await this.storage.get('currentSessionId')
    if (storedSessionId) {
      this.currentSessionId = storedSessionId
    }

    // Load session list
    await this.loadSessions()
  }

  /**
   * Load session list from backend
   *
   * Refreshes internal session list and emits sessionsLoaded event.
   *
   * @returns Promise resolving to array of sessions
   */
  async loadSessions(): Promise<ChatSession[]> {
    try {
      const sessions = await this.sessionService.getSessions()
      this.sessions = sessions
      this.emit(SessionEvent.SESSIONS_LOADED, { sessions } as SessionsLoadedPayload)
      return sessions
    } catch (error) {
      console.error('[SessionManager] Failed to load sessions:', error)
      throw error
    }
  }

  /**
   * Create a new session
   *
   * Creates session via backend API, updates storage, and emits sessionCreated event.
   *
   * @param name - Optional session name
   * @param workspaceRoot - Optional workspace root for the created session
   * @returns Promise resolving to new session ID
   */
  async createSession(name?: string, workspaceRoot?: string): Promise<string> {
    try {
      const effectiveWorkspaceRoot = workspaceRoot ?? this.defaultWorkspaceRoot
      const data = await this.sessionService.createSession(name, effectiveWorkspaceRoot)
      const sessionId = data.session_id

      // Update current session
      this.currentSessionId = sessionId
      await this.storage.set('currentSessionId', sessionId)

      // Create session object
      const newSession: ChatSession = {
        id: sessionId,
        name: name || `Session ${sessionId.slice(0, 8)}`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        llm_config: data.llm_config
      }

      // Emit event
      this.emit(SessionEvent.SESSION_CREATED, {
        sessionId,
        session: newSession
      } as SessionCreatedPayload)

      // Refresh session list
      await this.loadSessions()

      return sessionId
    } catch (error) {
      console.error('[SessionManager] Failed to create session:', error)
      throw error
    }
  }

  /**
   * Switch to a different session
   *
   * Updates backend, storage, and emits sessionSwitched event.
   * Also loads token usage for the new session.
   *
   * @param sessionId - ID of session to switch to
   */
  async switchSession(sessionId: string): Promise<void> {
    try {
      const previousSessionId = this.currentSessionId

      // Switch session on backend
      await this.sessionService.switchSession(sessionId)

      // Update current session
      this.currentSessionId = sessionId
      await this.storage.set('currentSessionId', sessionId)

      // Emit event
      this.emit(SessionEvent.SESSION_SWITCHED, {
        sessionId,
        previousSessionId
      } as SessionSwitchedPayload)

      // Load token usage for new session
      await this.loadTokenUsage(sessionId)
    } catch (error) {
      console.error('[SessionManager] Failed to switch session:', error)
      throw error
    }
  }

  /**
   * Delete a session
   *
   * Deletes session via backend API and handles cleanup.
   * If deleted session is current session, automatically switches to another session.
   *
   * @param sessionId - ID of session to delete
   */
  async deleteSession(sessionId: string): Promise<void> {
    try {
      // Delete session on backend
      await this.sessionService.deleteSession(sessionId)

      // Emit event
      this.emit(SessionEvent.SESSION_DELETED, {
        sessionId
      } as SessionDeletedPayload)

      // Refresh session list
      const updatedSessions = await this.loadSessions()

      // Handle current session deletion
      if (sessionId === this.currentSessionId) {
        this.emit(SessionEvent.CURRENT_SESSION_DELETED)

        // Switch to first available session or create new one
        if (updatedSessions.length > 0) {
          await this.switchSession(updatedSessions[0].id)
        } else {
          await this.createSession()
        }
      }

      // Clear token usage for deleted session
      this.tokenUsage.delete(sessionId)
    } catch (error) {
      console.error('[SessionManager] Failed to delete session:', error)
      throw error
    }
  }

  /**
   * Generate/refresh title for a session
   *
   * Requests backend to generate title, updates local session list.
   *
   * @param sessionId - ID of session to refresh title for
   */
  async refreshTitle(sessionId: string): Promise<void> {
    try {
      // HttpClient unwraps ApiResponse, so we get GenerateTitleData directly
      const data = await this.sessionService.generateTitle(sessionId)

      if (data.title) {
        // Update local session list
        this.sessions = this.sessions.map(session =>
          session.id === sessionId
            ? { ...session, name: data.title }
            : session
        )

        // Emit event
        this.emit(SessionEvent.TITLE_UPDATED, {
          sessionId,
          title: data.title
        } as TitleUpdatedPayload)
      }
    } catch (error) {
      console.error('[SessionManager] Failed to refresh title:', error)
      throw error
    }
  }

  /**
   * Load token usage for a session
   *
   * Fetches token usage from backend and caches it locally.
   *
   * @param sessionId - ID of session to load token usage for
   */
  async loadTokenUsage(sessionId: string): Promise<TokenUsage | null> {
    try {
      const usage = await this.sessionService.getTokenUsage(sessionId)
      this.tokenUsage.set(sessionId, usage)

      this.emit(SessionEvent.TOKEN_USAGE_UPDATED, {
        sessionId,
        usage
      } as TokenUsageUpdatedPayload)

      return usage
    } catch (error) {
      console.error('[SessionManager] Failed to load token usage:', error)
      this.tokenUsage.delete(sessionId)
      return null
    }
  }

  /**
   * Update token usage for current session
   *
   * Updates cached token usage and emits event.
   * Typically called in response to real-time updates from backend.
   *
   * @param usage - Updated token usage data
   */
  updateTokenUsage(usage: TokenUsage): void {
    if (this.currentSessionId) {
      this.tokenUsage.set(this.currentSessionId, usage)

      this.emit(SessionEvent.TOKEN_USAGE_UPDATED, {
        sessionId: this.currentSessionId,
        usage
      } as TokenUsageUpdatedPayload)
    }
  }

  /**
   * Get current session ID
   *
   * @returns Current session ID or null if none selected
   */
  getCurrentSessionId(): string | null {
    return this.currentSessionId
  }

  /**
   * Get session list
   *
   * @returns Array of sessions
   */
  getSessions(): ChatSession[] {
    return this.sessions
  }

  /**
   * Get token usage for a session
   *
   * Returns cached token usage data.
   *
   * @param sessionId - Session ID (defaults to current session)
   * @returns Token usage data or null if not loaded
   */
  getTokenUsage(sessionId?: string): TokenUsage | null {
    const targetSessionId = sessionId || this.currentSessionId
    if (!targetSessionId) return null
    return this.tokenUsage.get(targetSessionId) || null
  }

  /**
   * Clear all session data
   *
   * Clears current session, session list, and storage.
   */
  async clear(): Promise<void> {
    this.currentSessionId = null
    this.sessions = []
    this.tokenUsage.clear()
    await this.storage.clear()
  }
}
