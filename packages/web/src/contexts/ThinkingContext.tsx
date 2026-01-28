/**
 * Thinking Context for managing LLM thinking/reasoning mode
 *
 * This context provides global state management for the thinking feature,
 * allowing users to enable/disable extended thinking/reasoning mode in LLM responses.
 *
 * Thinking levels (for configurable mode):
 * - "default": Don't pass thinking params, use API's default behavior
 * - "low": Use low reasoning effort
 * - "high": Use high reasoning effort
 *
 * Provider-specific behavior:
 * - Google Gemini: thinking_config with thinking_level
 * - OpenAI: reasoning with effort
 * - Anthropic Claude: extended thinking with budget_tokens
 * - Moonshot K2.5: thinking type "enabled"/"disabled"
 */

import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react'
import { useSession } from './session/SessionContext'
import { useLlmConfig } from './LlmConfigContext'

/** Available thinking levels */
export type ThinkingLevel = 'default' | 'low' | 'high'

/** Thinking mode types */
export type ThinkingMode = 'none' | 'always_on' | 'configurable'

interface ThinkingContextType {
  /** Current thinking level */
  thinkingLevel: ThinkingLevel

  /** Thinking mode for the current model */
  thinkingMode: ThinkingMode

  /** Available thinking level options for the current model (only for 'configurable' mode) */
  thinkingOptions: ThinkingLevel[]

  /** Whether thinking is enabled (level != 'default') */
  thinkingEnabled: boolean

  /** Whether thinking is configurable for the current model */
  isConfigurable: boolean

  /** Update thinking level */
  setThinkingLevel: (level: ThinkingLevel) => void

  /** Toggle thinking between 'default' and 'high' */
  toggleThinking: () => void

  /** Whether a toggle operation is in progress */
  isToggling: boolean
}

const ThinkingContext = createContext<ThinkingContextType | undefined>(undefined)

interface ThinkingProviderProps {
  children: ReactNode
  /** Initial thinking level (default: 'high') */
  initialLevel?: ThinkingLevel
}

/**
 * Thinking Provider Component
 *
 * Provides thinking mode state management to the application.
 * Thinking is enabled by default (level='high') for enhanced LLM reasoning capabilities.
 * State is synced with backend via REST API for session-level persistence.
 */
export const ThinkingProvider: React.FC<ThinkingProviderProps> = ({
  children,
  initialLevel = 'high'
}) => {
  const [thinkingLevel, setThinkingLevelState] = useState<ThinkingLevel>(initialLevel)
  const [thinkingMode, setThinkingMode] = useState<ThinkingMode>('configurable')
  const [thinkingOptions, setThinkingOptions] = useState<ThinkingLevel[]>(['default', 'low', 'high'])
  const [isToggling, setIsToggling] = useState<boolean>(false)
  const { currentSessionId } = useSession()
  const { selectedProviderId, selectedModelId } = useLlmConfig()

  // Computed: whether thinking is enabled (any level except 'default')
  const thinkingEnabled = thinkingLevel !== 'default'

  // Computed: whether thinking is configurable
  const isConfigurable = thinkingMode === 'configurable'

  // Fetch thinking config from backend when session or model changes
  useEffect(() => {
    const fetchThinkingConfig = async () => {
      if (!currentSessionId) return

      try {
        // Build URL with provider and model params
        let url = `/api/llm-config/thinking?session_id=${encodeURIComponent(currentSessionId)}`
        if (selectedProviderId) {
          url += `&provider=${encodeURIComponent(selectedProviderId)}`
        }
        if (selectedModelId) {
          url += `&model=${encodeURIComponent(selectedModelId)}`
        }

        const response = await fetch(url)
        if (response.ok) {
          const data = await response.json()
          if (data.success && data.data) {
            // Use thinking_level from backend API
            const level = data.data.thinking_level as ThinkingLevel
            setThinkingLevelState(level || 'default')

            // Update mode if provided
            if (data.data.mode) {
              setThinkingMode(data.data.mode as ThinkingMode)
            }

            // Update available options if provided
            if (data.data.options && Array.isArray(data.data.options)) {
              setThinkingOptions(data.data.options as ThinkingLevel[])
            }
          }
        }
      } catch (error) {
        console.error('Failed to fetch thinking config:', error)
      }
    }

    fetchThinkingConfig()
  }, [currentSessionId, selectedProviderId, selectedModelId])

  // Listen for WebSocket thinking level updates
  useEffect(() => {
    const handleThinkingUpdate = (event: CustomEvent) => {
      const { thinking_level } = event.detail
      if (typeof thinking_level === 'string') {
        setThinkingLevelState(thinking_level as ThinkingLevel)
      }
    }

    window.addEventListener('thinking_config_updated' as any, handleThinkingUpdate as any)
    return () => {
      window.removeEventListener('thinking_config_updated' as any, handleThinkingUpdate as any)
    }
  }, [])

  const setThinkingLevel = useCallback(async (level: ThinkingLevel) => {
    if (!currentSessionId) {
      console.warn('Cannot update thinking config: no session ID')
      return
    }

    // Only allow changes for configurable mode
    if (thinkingMode !== 'configurable') {
      console.warn(`Cannot change thinking level: mode is '${thinkingMode}'`)
      return
    }

    setIsToggling(true)
    try {
      // Build URL with provider and model params
      let url = `/api/llm-config/thinking?session_id=${encodeURIComponent(currentSessionId)}`
      if (selectedProviderId) {
        url += `&provider=${encodeURIComponent(selectedProviderId)}`
      }
      if (selectedModelId) {
        url += `&model=${encodeURIComponent(selectedModelId)}`
      }

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ thinking_level: level }),
      })

      if (response.ok) {
        const data = await response.json()
        if (data.success && data.data) {
          setThinkingLevelState(data.data.thinking_level as ThinkingLevel)
          console.log(`Thinking level set to '${level}'`)
        }
      } else {
        console.error('Failed to update thinking config:', response.statusText)
      }
    } catch (error) {
      console.error('Failed to update thinking config:', error)
    } finally {
      setIsToggling(false)
    }
  }, [currentSessionId, selectedProviderId, selectedModelId, thinkingMode])

  const toggleThinking = useCallback(() => {
    if (!isConfigurable) return
    setThinkingLevel(thinkingEnabled ? 'default' : 'high')
  }, [thinkingEnabled, setThinkingLevel, isConfigurable])

  const value: ThinkingContextType = {
    thinkingLevel,
    thinkingMode,
    thinkingOptions,
    thinkingEnabled,
    isConfigurable,
    setThinkingLevel,
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
