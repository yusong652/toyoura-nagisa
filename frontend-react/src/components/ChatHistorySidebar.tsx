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
    try {
      setIsCreating(true)
      await createNewSession(newSessionName || undefined)
      setNewSessionName('')
      clearChat()
    } catch (error) {
      console.error('创建会话失败:', error)
    } finally {
      setIsCreating(false)
    }
  }

  const handleSwitchSession = async (sessionId: string) => {
    try {
      await switchSession(sessionId)
      closeSidebar()
    } catch (error) {
      console.error('切换会话失败:', error)
    }
  }

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation() // 防止触发切换会话
    
    if (window.confirm('确定要删除这个会话吗？')) {
      try {
        await deleteSession(sessionId)
      } catch (error) {
        console.error('删除会话失败:', error)
      }
    }
  }

  // 格式化日期
  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
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