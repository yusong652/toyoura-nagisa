import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { toolService } from '@aiNagisa/core'

interface TtsEnableContextType {
  ttsEnabled: boolean
  updateTTSEnabled: (enabled: boolean) => Promise<void>
}

const TtsEnableContext = createContext<TtsEnableContextType | undefined>(undefined)

export const useTtsEnable = (): TtsEnableContextType => {
  const context = useContext(TtsEnableContext)
  if (!context) {
    throw new Error('useTtsEnable must be used within a TtsEnableProvider')
  }
  return context
}

interface TtsEnableProviderProps {
  children: ReactNode
}

export const TtsEnableProvider: React.FC<TtsEnableProviderProps> = ({ children }) => {
  // TTS enabled state, default to true
  const [ttsEnabled, setTtsEnabled] = useState<boolean>(true)

  // Update TTS enabled status
  const updateTTSEnabled = useCallback(async (enabled: boolean): Promise<void> => {
    try {
      const data = await toolService.updateTtsEnabled(enabled)
      setTtsEnabled(data.tts_enabled)
    } catch (error) {
      console.error('Error updating TTS status:', error)
      throw error
    }
  }, [])

  return (
    <TtsEnableContext.Provider value={{
      ttsEnabled,
      updateTTSEnabled
    }}>
      {children}
    </TtsEnableContext.Provider>
  )
}