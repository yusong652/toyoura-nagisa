/**
 * Memory Context for managing memory injection state
 * 
 * This context provides global state management for the memory feature,
 * allowing users to enable/disable memory injection in AI responses.
 */

import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react'

interface MemoryContextType {
  /** Whether memory injection is enabled */
  memoryEnabled: boolean
  
  /** Update memory enabled state */
  setMemoryEnabled: (enabled: boolean) => void
  
  /** Toggle memory enabled state */
  toggleMemory: () => void
}

const MemoryContext = createContext<MemoryContextType | undefined>(undefined)

interface MemoryProviderProps {
  children: ReactNode
  /** Initial memory enabled state (default: true) */
  initialEnabled?: boolean
}

/**
 * Memory Provider Component
 * 
 * Provides memory state management to the application.
 * Memory is enabled by default to maintain conversation context.
 */
export const MemoryProvider: React.FC<MemoryProviderProps> = ({ 
  children, 
  initialEnabled = true 
}) => {
  const [memoryEnabled, setMemoryEnabledState] = useState<boolean>(initialEnabled)

  const setMemoryEnabled = useCallback((enabled: boolean) => {
    setMemoryEnabledState(enabled)
    // Could add localStorage persistence here if needed
    // localStorage.setItem('memoryEnabled', enabled.toString())
  }, [])

  const toggleMemory = useCallback(() => {
    setMemoryEnabled(!memoryEnabled)
  }, [memoryEnabled, setMemoryEnabled])

  const value: MemoryContextType = {
    memoryEnabled,
    setMemoryEnabled,
    toggleMemory
  }

  return (
    <MemoryContext.Provider value={value}>
      {children}
    </MemoryContext.Provider>
  )
}

/**
 * Hook to use memory context
 * 
 * @returns Memory context value
 * @throws Error if used outside of MemoryProvider
 */
export const useMemory = (): MemoryContextType => {
  const context = useContext(MemoryContext)
  if (!context) {
    throw new Error('useMemory must be used within a MemoryProvider')
  }
  return context
}