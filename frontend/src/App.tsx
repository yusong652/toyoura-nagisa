import React, { useEffect } from 'react'
import './App.css'
import ChatBox from './components/ChatBox'
import InputArea from './components/InputArea'
import Live2DCanvas from './components/Live2DCanvas'
import ChatHistorySidebar from './components/ChatHistorySidebar'
import ThemeToggle from './components/ThemeToggle'
import ConnectionError from './components/ConnectionError'
import { AudioProvider } from './contexts/AudioContext'
import { ChatProvider, useChat } from './contexts/ChatContext'
import { ConnectionStatus } from './types/chat'
import GeolocationService from './utils/geolocation'

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
  // 初始化主题和地理位置服务
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light'
    document.body.setAttribute('data-theme', savedTheme)
    
    // 初始化地理位置服务
    const initGeolocation = async () => {
      try {
        const geolocationService = GeolocationService.getInstance()
        await geolocationService.initialize()
        
        // 如果用户已经授权，自动获取位置
        if (geolocationService.getPermissionStatus() === 'granted') {
          await geolocationService.getAndUpdateLocation()
        }
      } catch (error) {
        console.warn('Failed to initialize geolocation service:', error)
      }
    }
    
    initGeolocation()
  }, [])

  return (
    <>
      <AudioProvider>
        <ChatProvider>
          <AppContent />
          <Live2DCanvas />
        </ChatProvider>
      </AudioProvider>
    </>
  )
}

export default App 