import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { useSession } from '../session/SessionContext'

// Types based on backend API
export interface ModelInfo {
  id: string
  name: string
  description?: string
  context_window?: number
  is_thinking?: boolean // Whether model supports thinking natively
}

export interface ProviderInfo {
  name: string
  provider: string // id
  models: ModelInfo[]
}

interface LlmConfigContextType {
  providers: ProviderInfo[]
  selectedProviderId: string | null
  selectedModelId: string | null
  isLoading: boolean
  error: string | null
  
  // Actions
  selectProvider: (providerId: string) => void
  selectModel: (modelId: string) => void
  updateSessionConfig: (providerId: string, modelId: string) => Promise<void>
}

const LlmConfigContext = createContext<LlmConfigContextType | undefined>(undefined)

export const useLlmConfig = (): LlmConfigContextType => {
  const context = useContext(LlmConfigContext)
  if (!context) {
    throw new Error('useLlmConfig must be used within a LlmConfigProvider')
  }
  return context
}

interface LlmConfigProviderProps {
  children: ReactNode
}

const STORAGE_KEY_PROVIDER = 'nagisa_last_provider'
const STORAGE_KEY_MODEL = 'nagisa_last_model'

export const LlmConfigProvider: React.FC<LlmConfigProviderProps> = ({ children }) => {
  const [providers, setProviders] = useState<ProviderInfo[]>([])
  const [selectedProviderId, setSelectedProviderId] = useState<string | null>(
    localStorage.getItem(STORAGE_KEY_PROVIDER)
  )
  const [selectedModelId, setSelectedModelId] = useState<string | null>(
    localStorage.getItem(STORAGE_KEY_MODEL)
  )
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const { currentSessionId } = useSession()

  // Load providers
  useEffect(() => {
    const fetchProviders = async () => {
      setIsLoading(true)
      try {
        const response = await fetch('/api/llm-config/providers')
        if (response.ok) {
          const data = await response.json()
          if (data.success && data.data) {
            setProviders(data.data.providers)
            
            // If no selection yet, verify if localStorage selection is valid
            // If not valid, default to first provider/model
            if (data.data.providers.length > 0) {
              const currentProvider = data.data.providers.find((p: ProviderInfo) => p.provider === selectedProviderId)
              if (!currentProvider) {
                // Default to first
                const first = data.data.providers[0]
                setSelectedProviderId(first.provider)
                setSelectedModelId(first.models[0]?.id || null)
              } else {
                // Verify model
                const validModel = currentProvider.models.find((m: ModelInfo) => m.id === selectedModelId)
                if (!validModel) {
                  setSelectedModelId(currentProvider.models[0]?.id || null)
                }
              }
            }
          }
        }
      } catch (err) {
        console.error('Failed to fetch providers:', err)
        setError('Failed to load LLM providers')
      } finally {
        setIsLoading(false)
      }
    }
    
    fetchProviders()
  }, []) // Run once on mount

  // Sync with Session Config when session changes
  useEffect(() => {
    const fetchSessionConfig = async () => {
      if (!currentSessionId) return

      try {
        const response = await fetch(`/api/llm-config?session_id=${encodeURIComponent(currentSessionId)}`)
        if (response.ok) {
          const data = await response.json()
          if (data.success && data.data) {
            // Backend returns config for this session
            // If session has specific config, use it. 
            // Otherwise, we might want to apply our local defaults to the session?
            // Usually session config overrides local default for display
            if (data.data.provider) {
              setSelectedProviderId(data.data.provider)
              localStorage.setItem(STORAGE_KEY_PROVIDER, data.data.provider)
            }
            if (data.data.model) {
              setSelectedModelId(data.data.model)
              localStorage.setItem(STORAGE_KEY_MODEL, data.data.model)
            }
          }
        }
      } catch (err) {
        console.error('Failed to fetch session LLM config:', err)
      }
    }

    if (currentSessionId) {
      fetchSessionConfig()
    }
  }, [currentSessionId])

  const selectProvider = useCallback((providerId: string) => {
    setSelectedProviderId(providerId)
    localStorage.setItem(STORAGE_KEY_PROVIDER, providerId)
    
    // Auto-select first model for this provider
    const provider = providers.find(p => p.provider === providerId)
    if (provider && provider.models.length > 0) {
      const firstModel = provider.models[0].id
      setSelectedModelId(firstModel)
      localStorage.setItem(STORAGE_KEY_MODEL, firstModel)
    } else {
      setSelectedModelId(null)
    }
  }, [providers])

  const selectModel = useCallback((modelId: string) => {
    setSelectedModelId(modelId)
    localStorage.setItem(STORAGE_KEY_MODEL, modelId)
  }, [])

  const updateSessionConfig = useCallback(async (providerId: string, modelId: string) => {
    if (!currentSessionId) return

    try {
      // Update local state first (optimistic)
      selectProvider(providerId)
      selectModel(modelId)

      // Send to backend
      const response = await fetch(`/api/llm-config?session_id=${encodeURIComponent(currentSessionId)}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          provider: providerId,
          model: modelId,
          // We preserve secondary model if it exists in backend, or send current
          // For now just sending primary
        }),
      })
      
      if (!response.ok) {
        throw new Error('Failed to update session config')
      }
      
      console.log(`Updated session ${currentSessionId} to ${providerId}/${modelId}`)
      
    } catch (err) {
      console.error('Failed to update session config:', err)
      setError('Failed to save configuration')
    }
  }, [currentSessionId, selectProvider, selectModel])

  return (
    <LlmConfigContext.Provider value={{
      providers,
      selectedProviderId,
      selectedModelId,
      isLoading,
      error,
      selectProvider,
      selectModel,
      updateSessionConfig
    }}>
      {children}
    </LlmConfigContext.Provider>
  )
}
