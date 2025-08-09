import React, { useEffect } from 'react'
import './App.css'
import ChatBox from './components/ChatBox'
import InputArea from './components/InputArea'
import Live2DCanvas from './components/Live2DCanvas'
import ChatHistorySidebar from './components/ChatHistorySidebar'
import ThemeToggle from './components/ThemeToggle'
import ConnectionError from './components/ConnectionError'
import { AudioProvider } from './contexts/audio/AudioContext'
import { ConnectionProvider } from './contexts/connection/ConnectionContext'
import { ToolsProvider } from './contexts/tools/ToolsContext'
import { SessionProvider } from './contexts/session/SessionContext'
import { ChatProvider } from './contexts/chat/ChatContext'
import { useConnection } from './contexts/connection/ConnectionContext'
import { ConnectionStatus } from './types/connection'

function AppContent(): React.ReactElement {
  const { connectionStatus, connectionError, checkConnection } = useConnection()

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
        <ConnectionProvider>
          <ToolsProvider>
            <SessionProvider>
              <ChatProvider>
                <AppContent />
                <Live2DCanvas />
              </ChatProvider>
            </SessionProvider>
          </ToolsProvider>
        </ConnectionProvider>
      </AudioProvider>
    </>
  )
}

export default App 