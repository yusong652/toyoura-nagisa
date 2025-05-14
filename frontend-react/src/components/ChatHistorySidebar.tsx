import React, { useState } from 'react'
import './ChatHistorySidebar.css'

interface ChatHistoryItem {
  id: string
  title: string
  preview: string
}

const ChatHistorySidebar: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false)
  
  // 示例聊天历史数据
  const sampleItems: ChatHistoryItem[] = [
    { id: '1', title: '日常对话', preview: '你好，今天天气真不错！' },
    { id: '2', title: '学习讨论', preview: '关于Python的异步编程...' },
    { id: '3', title: '闲聊', preview: '最近有什么好看的电影推荐吗？' }
  ]

  const toggleSidebar = () => {
    setIsOpen(!isOpen)
    document.body.classList.toggle('sidebar-open')
  }

  const closeSidebar = () => {
    setIsOpen(false)
    document.body.classList.remove('sidebar-open')
  }

  return (
    <>
      <button className="chat-history-toggle" onClick={toggleSidebar}>
        ☰
      </button>
      
      <div className={`chat-history-sidebar ${isOpen ? 'open' : ''}`}>
        <div className="chat-history-header">
          <div className="chat-history-title">聊天记录</div>
          <button 
            className="chat-history-close"
            onClick={closeSidebar}
          >
            ×
          </button>
        </div>
        
        <div className="chat-history-list">
          {sampleItems.map(item => (
            <div key={item.id} className="chat-history-item">
              <div className="chat-history-item-title">{item.title}</div>
              <div className="chat-history-item-preview">{item.preview}</div>
            </div>
          ))}
        </div>
      </div>
    </>
  )
}

export default ChatHistorySidebar 