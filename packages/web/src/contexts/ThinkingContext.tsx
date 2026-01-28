/**
 * Thinking Context for managing LLM thinking/reasoning mode
 *
 * This context provides global state management for the thinking feature,
 * allowing users to enable/disable extended thinking/reasoning mode in LLM responses.
 *
 * Provider-specific behavior when thinking is enabled:
 * - Google Gemini: thinking_config with thinking_level "high"
 * - OpenAI: reasoning with effort "medium"
 * - Anthropic Claude: extended thinking with budget_tokens
 * - Moonshot K2.5: thinking type "enabled"
 */

import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react'
import { useSession } from './session/SessionContext'

interface ThinkingContextType {
  /** Whether thinking/reasoning mode is enabled */
  thinkingEnabled: boolean

  /** Update thinking enabled state */
  setThinkingEnabled: (enabled: boolean) => void

  /** Toggle thinking enabled state */
  toggleThinking: () => void

  /** Whether a toggle operation is in progress */
  isToggling: boolean
}

const ThinkingContext = createContext<ThinkingContextType | undefined>(undefined)

interface ThinkingProviderProps {
  children: ReactNode
  /** Initial thinking enabled state (default: true) */
  initialEnabled?: boolean
}

/**
 * Thinking Provider Component
 *
 * Provides thinking mode state management to the application.
 * Thinking is enabled by default for enhanced LLM reasoning capabilities.
 * State is synced with backend via REST API for session-level persistence.
 */
export const ThinkingProvider: React.FC<ThinkingProviderProps> = ({
  children,
  initialEnabled = true
}) => {
  const [thinkingEnabled, setThinkingEnabledState] = useState<boolean>(initialEnabled)
  const [isToggling, setIsToggling] = useState<boolean>(false)
  const { currentSessionId } = useSession()

  // Fetch initial thinking config from backend when session changes
  useEffect(() => {
    const fetchThinkingConfig = async () => {
      if (!currentSessionId) return

      try {
        const response = await fetch(
          `/api/llm-config/thinking?session_id=${encodeURIComponent(currentSessionId)}`
        )
        if (response.ok) {
          const data = await response.json()
          if (data.success && data.data) {
            setThinkingEnabledState(data.data.thinking_enabled)
          }
        }
      } catch (error) {
        console.error('Failed to fetch thinking config:', error)
      }
    }

    fetchThinkingConfig()
  }, [currentSessionId])

  // Listen for WebSocket thinking config updates
  useEffect(() => {
    const handleThinkingUpdate = (event: CustomEvent) => {
      const { thinking_enabled } = event.detail
      if (typeof thinking_enabled === 'boolean') {
        setThinkingEnabledState(thinking_enabled)
      }
    }

    window.addEventListener('thinkingConfigUpdate', handleThinkingUpdate as EventListener)

    return () => {
      window.removeEventListener('thinkingConfigUpdate', handleThinkingUpdate as EventListener)
    }
  }, [])

  const setThinkingEnabled = useCallback(async (enabled: boolean) => {
    if (!currentSessionId) {
      console.warn('Cannot update thinking config: no session ID')
      return
    }

    setIsToggling(true)
    try {
      const response = await fetch(
        `/api/llm-config/thinking?session_id=${encodeURIComponent(currentSessionId)}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ thinking_enabled: enabled }),
        }
      )

      if (response.ok) {
        const data = await response.json()
        if (data.success && data.data) {
          setThinkingEnabledState(data.data.thinking_enabled)
          console.log(`Thinking mode ${enabled ? 'enabled' : 'disabled'}`)
        }
      } else {
        console.error('Failed to update thinking config:', response.statusText)
      }
    } catch (error) {
      console.error('Failed to update thinking config:', error)
    } finally {
      setIsToggling(false)
    }
  }, [currentSessionId])

  const toggleThinking = useCallback(() => {
    setThinkingEnabled(!thinkingEnabled)
  }, [thinkingEnabled, setThinkingEnabled])

  const value: ThinkingContextType = {
    thinkingEnabled,
    setThinkingEnabled,
    toggleThinking,
    isToggling
  }

  return (
    <ThinkingContext.Provider value={value}>
      {children}
    </ThinkingContext.Provider>
  )
}

/**
 * Hook to use thinking context
 *
 * @returns Thinking context value
 * @throws Error if used outside of ThinkingProvider
 */
export const useThinking = (): ThinkingContextType => {
  const context = useContext(ThinkingContext)
  if (!context) {
    throw new Error('useThinking must be used within a ThinkingProvider')
  }
  return context
}
