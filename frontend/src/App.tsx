import React, { useEffect } from 'react'
import './App.css'
import ChatBox from './components/ChatBox'
import InputArea from './components/InputArea'
import Live2DCanvas from './components/Live2DCanvas'
import ChatHistorySidebar from './components/ChatHistorySidebar'
import ThemeToggle from './components/ThemeToggle'
import ConnectionError from './components/ConnectionError'
import { AudioProvider } from './contexts/AudioContext'
import { ConnectionProvider } from './contexts/ConnectionContext'
import { ToolsProvider } from './contexts/ToolsContext'
import { SessionProvider } from './contexts/SessionContext'
import { ChatProvider, useChat } from './contexts/ChatContext'
import { ConnectionStatus } from './types/chat'

function AppContent(): React.ReactElement {
  const { connectionStatus, connectionError, checkConnection } = useChat()

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