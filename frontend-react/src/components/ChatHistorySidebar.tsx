import React, { useState } from 'react'
import './ChatHistorySidebar.css'
import { useChat } from '../contexts/ChatContext'
import { ChatSession } from '../types/chat'

const ChatHistorySidebar: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false)
  const [newSessionName, setNewSessionName] = useState('')
  const [isCreating, setIsCreating] = useState(false)
  
  const { 
    sessions, 
    currentSessionId, 
    createNewSession, 
    switchSession, 
    deleteSession,
    clearChat
  } = useChat()

  const toggleSidebar = () => {
    setIsOpen(!isOpen)
    document.body.classList.toggle('sidebar-open')
  }

  const closeSidebar = () => {
    setIsOpen(false)
    document.body.classList.remove('sidebar-open')
  }

  const handleCreateSession = async () => {
    if (!newSessionName.trim()) return
    setIsCreating(true)
    try {
      await createNewSession(newSessionName)
      setNewSessionName('')
    } finally {
      setIsCreating(false)
    }
  }

  const handleSwitchSession = (sessionId: string) => {
    switchSession(sessionId)
    closeSidebar()
  }

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation()
    if (window.confirm('确定要删除这个会话吗？')) {
      await deleteSession(sessionId)
    }
  }

  // 格式化日期
  const formatDate = (date: string) => {
    return new Date(date).toLocaleString()
  }

  return (
    <>
      <button className="history-toggle" onClick={toggleSidebar} aria-label="Toggle chat history">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="3" y1="12" x2="21" y2="12"></line>
          <line x1="3" y1="6" x2="21" y2="6"></line>
          <line x1="3" y1="18" x2="21" y2="18"></line>
        </svg>
      </button>
      
      <div className={`chat-history-sidebar ${isOpen ? 'open' : ''}`}>
        <div className="chat-history-header">
          <div className="chat-history-title">聊天记录</div>
          <button 
            className="chat-history-close"
            onClick={closeSidebar}
            aria-label="关闭聊天记录"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M2 2L12 12M2 12L12 2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        </div>
        
        <div className="chat-history-actions">
          <div className="new-session-input-container">
            <input
              type="text"
              placeholder="新会话名称"
              value={newSessionName}
              onChange={(e) => setNewSessionName(e.target.value)}
              className="new-session-input"
            />
            <button 
              className="new-session-button"
              onClick={handleCreateSession}
              disabled={isCreating}
            >
              {isCreating ? '创建中...' : '新建'}
            </button>
          </div>
        </div>
        
        <div className="chat-history-list">
          {sessions.length === 0 ? (
            <div className="no-sessions-message">暂无聊天记录</div>
          ) : (
            sessions.map((session: ChatSession) => (
              <div 
                key={session.id} 
                className={`chat-history-item ${currentSessionId === session.id ? 'active' : ''}`}
                onClick={() => handleSwitchSession(session.id)}
              >
                <div className="chat-history-item-title">{session.name}</div>
                <div className="chat-history-item-preview">
                  {formatDate(session.updated_at)}
                </div>
                <button 
                  className="delete-session-button"
                  onClick={(e) => handleDeleteSession(e, session.id)}
                >
                  🗑️
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  )
}

export default ChatHistorySidebar