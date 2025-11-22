import React, { useEffect } from 'react'
import './App.css'
import { ChatBox } from './components/ChatBox'
import InputArea from './components/InputArea'
import { SlashCommandStatusPanel } from './components/SlashCommandStatusPanel'
import Live2DCanvas from './components/Live2DCanvas'
import ChatHistorySidebar from './components/ChatHistorySidebar/ChatHistorySidebar'
import BackgroundTaskMonitor from './components/BackgroundTaskMonitor'
import { ThemeToggle } from './components/Toggle/variants/ThemeToggle'
import ConnectionError from './components/ConnectionError'
import { useSlashCommandExecution } from './components/InputArea/hooks'
import { AudioProvider } from './contexts/audio/AudioContext'
import { TtsEnableProvider } from './contexts/audio/TtsEnableContext'
import { ConnectionProvider } from './contexts/connection/ConnectionContext'
import { AgentProvider } from './contexts/agent/AgentContext'
import { SessionProvider } from './contexts/session/SessionContext'
import { ChatProvider } from './contexts/chat/ChatContext'
import { Live2DProvider } from './contexts/live2d/Live2DContext'
import { MemoryProvider } from './contexts/MemoryContext'
import { useConnection } from './contexts/connection/ConnectionContext'
import { ConnectionStatus } from './types/connection'

function AppContent(): React.ReactElement {
  const { connectionStatus, connectionError, checkConnection, sendWebSocketMessage, sessionId } = useConnection()

  const { executeSlashCommand, executionQueue } = useSlashCommandExecution()

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

  return (
    <div className="app-container">
      <ThemeToggle />
      <div className="chat-container">
        <div className="chat-left-panel">
          <ChatBox
            statusPanel={
              <SlashCommandStatusPanel
                executionQueue={executionQueue}
                position="chatbox-right"
              />
            }
          />
          <InputArea executeSlashCommand={executeSlashCommand} />
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
      <AudioProvider>
        <TtsEnableProvider>
          <ConnectionProvider>
            <AgentProvider>
              <SessionProvider>
                <MemoryProvider>
                  <ChatProvider>
                    <Live2DProvider>
                      <AppContent />
                      <Live2DCanvas />
                    </Live2DProvider>
                  </ChatProvider>
                </MemoryProvider>
              </SessionProvider>
            </AgentProvider>
          </ConnectionProvider>
        </TtsEnableProvider>
      </AudioProvider>
    </>
  )
}

export default App 