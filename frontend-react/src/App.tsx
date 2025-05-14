import React, { useEffect } from 'react'
import './App.css'
import ChatBox from './components/ChatBox'
import InputArea from './components/InputArea'
import Live2DCanvas from './components/Live2DCanvas'
import ChatHistorySidebar from './components/ChatHistorySidebar'
import ThemeToggle from './components/ThemeToggle'
import { AudioProvider } from './contexts/AudioContext'
import { ChatProvider } from './contexts/ChatContext'

function App(): React.ReactElement {
  // 初始化主题
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'light'
    document.body.setAttribute('data-theme', savedTheme)
  }, [])

  return (
    <>
      <AudioProvider>
        <ChatProvider>
          <div className="app-container">
            <ThemeToggle />
            {/* <h1>aiNagisa</h1> */}
            <div className="chat-container">
              <div className="chat-left-panel">
                <ChatBox />
                <InputArea />
              </div>
            </div>
            <ChatHistorySidebar />
          </div>
          <Live2DCanvas />
        </ChatProvider>
      </AudioProvider>
    </>
  )
}

export default App 