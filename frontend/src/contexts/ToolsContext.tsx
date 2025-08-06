import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { toolService } from '../services/api'

export interface ToolState {
  type: 'NAGISA_IS_USING_TOOL' | 'NAGISA_TOOL_USE_CONCLUDED'
  tool_name?: string
  parameters?: Record<string, any>
  action_text?: string
}

export interface ToolsContextType {
  // 工具状态
  toolState: ToolState | null
  toolsEnabled: boolean
  ttsEnabled: boolean

  // 工具操作
  updateToolsEnabled: (enabled: boolean) => Promise<void>
  updateTtsEnabled: (enabled: boolean) => Promise<void>
  setToolState: (state: ToolState | null) => void
}

const ToolsContext = createContext<ToolsContextType | undefined>(undefined)

export const useTools = (): ToolsContextType => {
  const context = useContext(ToolsContext)
  if (!context) {
    throw new Error('useTools must be used within a ToolsProvider')
  }
  return context
}

interface ToolsProviderProps {
  children: ReactNode
}

export const ToolsProvider: React.FC<ToolsProviderProps> = ({ children }) => {
  // 工具状态管理
  const [toolState, setToolState] = useState<ToolState | null>(null)
  const [toolsEnabled, setToolsEnabled] = useState<boolean>(false)
  const [ttsEnabled, setTtsEnabled] = useState<boolean>(true)

  // 更新工具开启状态
  const updateToolsEnabled = useCallback(async (enabled: boolean): Promise<void> => {
    try {
      const data = await toolService.updateToolsEnabled(enabled)
      if (data.success) {
        setToolsEnabled(data.tools_enabled)
      }
    } catch (error) {
      console.error('更新工具状态失败:', error)
      throw error
    }
  }, [])

  // 更新 TTS 状态
  const updateTtsEnabled = useCallback(async (enabled: boolean): Promise<void> => {
    try {
      const data = await toolService.updateTtsEnabled(enabled)
      setTtsEnabled(data.tts_enabled)
    } catch (error) {
      console.error('Error updating TTS status:', error)
      throw error
    }
  }, [])

  return (
    <ToolsContext.Provider value={{
      toolState,
      toolsEnabled,
      ttsEnabled,
      updateToolsEnabled,
      updateTtsEnabled,
      setToolState
    }}>
      {children}
    </ToolsContext.Provider>
  )
}