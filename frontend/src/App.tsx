import React, { useEffect } from 'react'
import './App.css'
import { ChatBox } from './components/ChatBox'
import InputArea from './components/InputArea'
import { SlashCommandStatusPanel } from './components/SlashCommandStatusPanel'
import Live2DCanvas from './components/Live2DCanvas'
import ChatHistorySidebar from './components/ChatHistorySidebar'
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
import { useConnection } from './contexts/connection/ConnectionContext'
import { ConnectionStatus } from './types/connection'

function AppContent(): React.ReactElement {
  const { connectionStatus, connectionError, checkConnection } = useConnection()
  
  // Slash command execution hook - shared between InputArea and StatusPanel
  const { executeSlashCommand, executionQueue } = useSlashCommandExecution()

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
  // 初始化主题
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
                <ChatProvider>
                  <Live2DProvider>
                    <AppContent />
                    <Live2DCanvas />
                  </Live2DProvider>
                </ChatProvider>
              </SessionProvider>
            </AgentProvider>
          </ConnectionProvider>
        </TtsEnableProvider>
      </AudioProvider>
    </>
  )
}

export default App 