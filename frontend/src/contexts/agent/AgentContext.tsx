import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { toolService } from '../../services/api'
import { ToolState } from '../../types/tools'

interface AgentContextType {
  // Tool-related state
  toolState: ToolState | null
  toolsEnabled: boolean
  updateToolsEnabled: (enabled: boolean) => Promise<void>
  setToolState: (state: ToolState | null) => void
  // Future: agent profile, model selection, etc. can be added here
}

const AgentContext = createContext<AgentContextType | undefined>(undefined)

export const useAgent = (): AgentContextType => {
  const context = useContext(AgentContext)
  if (!context) {
    throw new Error('useAgent must be used within an AgentProvider')
  }
  return context
}

interface AgentProviderProps {
  children: ReactNode
}

export const AgentProvider: React.FC<AgentProviderProps> = ({ children }) => {
  // Tool state management
  const [toolState, setToolState] = useState<ToolState | null>(null)
  const [toolsEnabled, setToolsEnabled] = useState<boolean>(false)

  // Update tools enabled status
  const updateToolsEnabled = useCallback(async (enabled: boolean): Promise<void> => {
    try {
      const data = await toolService.updateToolsEnabled(enabled)
      if (data.success) {
        setToolsEnabled(data.tools_enabled)
      }
    } catch (error) {
      console.error('Failed to update tools status:', error)
      throw error
    }
  }, [])

  return (
    <AgentContext.Provider value={{
      toolState,
      toolsEnabled,
      updateToolsEnabled,
      setToolState
    }}>
      {children}
    </AgentContext.Provider>
  )
}