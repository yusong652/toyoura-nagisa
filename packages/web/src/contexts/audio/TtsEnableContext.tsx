import React, { createContext, useContext, useState, ReactNode } from 'react'

interface TtsEnableContextType {
  ttsEnabled: boolean
  setTtsEnabled: (enabled: boolean) => void
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
  const [ttsEnabled, setTtsEnabled] = useState<boolean>(true)

  return (
    <TtsEnableContext.Provider value={{ ttsEnabled, setTtsEnabled }}>
      {children}
    </TtsEnableContext.Provider>
  )
}
