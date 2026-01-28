import React, { useEffect } from 'react'
import './App.css'
import './styles/markdown.css'
import { ChatBox } from './components/ChatBox'
import InputArea from './components/InputArea'
import ChatHistorySidebar from './components/ChatHistorySidebar/ChatHistorySidebar'
import BackgroundTaskMonitor from './components/BackgroundTaskMonitor'
import { ThemeToggle } from './components/Toggle/variants/ThemeToggle'
import ConnectionError from './components/ConnectionError'
import { ConnectionProvider } from './contexts/connection/ConnectionContext'
import { SessionProvider } from './contexts/session/SessionContext'
import { ChatProvider } from './contexts/chat/ChatContext'
import { MemoryProvider } from './contexts/MemoryContext'
import { ThinkingProvider, useThinking } from './contexts/ThinkingContext'
import { useConnection } from './contexts/connection/ConnectionContext'
import { ConnectionStatus } from './types/connection'

function AppContent(): React.ReactElement {
  const { connectionStatus, connectionError, checkConnection, sendWebSocketMessage, sessionId } = useConnection()
  const { toggleThinking, thinkingEnabled, isToggling } = useThinking()

  // Global ESC key listener for interrupt
  useEffect(() => {
    const handleEscKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        console.log('[App] ESC key pressed - sending interrupt signal')

        // Send USER_INTERRUPT message via WebSocket
        if (sendWebSocketMessage && sessionId) {
          sendWebSocketMessage({
            type: 'USER_INTERRUPT',
            session_id: sessionId,
            timestamp: new Date().toISOString()
          })
          console.log('[App] USER_INTERRUPT sent to backend')
        } else {
          console.warn('[App] Cannot send interrupt: WebSocket or sessionId not available')
        }
      }
    }

    window.addEventListener('keydown', handleEscKey)
    return () => window.removeEventListener('keydown', handleEscKey)
  }, [sendWebSocketMessage, sessionId])

  // Global Ctrl+T listener for thinking mode toggle
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+T (or Cmd+T on Mac) to toggle thinking mode
      if ((e.ctrlKey || e.metaKey) && e.key === 't') {
        e.preventDefault()
        if (!isToggling) {
          toggleThinking()
          console.log(`[App] Thinking mode toggled to: ${!thinkingEnabled}`)
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [toggleThinking, thinkingEnabled, isToggling])

  return (
    <div className="app-container">
      <ThemeToggle />
      <div className="chat-container">
        <div className="chat-left-panel">
          <ChatBox />
          <InputArea />
        </div>
      </div>
      <ChatHistorySidebar />
      <BackgroundTaskMonitor />
      {connectionStatus !== ConnectionStatus.CONNECTED && connectionError && (
        <ConnectionError
          message={connectionError}
          onRetry={checkConnection}
        />
      )}
    </div>
  )
}

function App(): React.ReactElement {
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light'
    document.body.setAttribute('data-theme', savedTheme)
  }, [])

  return (
    <>
      <ConnectionProvider>
        <SessionProvider>
          <ThinkingProvider>
            <MemoryProvider>
              <ChatProvider>
                <AppContent />
              </ChatProvider>
            </MemoryProvider>
          </ThinkingProvider>
        </SessionProvider>
      </ConnectionProvider>
    </>
  )
}

export default App 
