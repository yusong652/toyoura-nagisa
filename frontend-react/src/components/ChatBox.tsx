import React, { useEffect, useRef } from 'react'
import { useChat } from '../contexts/ChatContext'
import MessageItem from './MessageItem'
import './ChatBox.css'

const ChatBox: React.FC = () => {
  const { messages, isLoading } = useChat()
  const chatboxRef = useRef<HTMLDivElement>(null)

  // 滚动到底部
  useEffect(() => {
    if (chatboxRef.current) {
      chatboxRef.current.scrollTop = chatboxRef.current.scrollHeight
    }
  }, [messages, isLoading])

  return (
    <div className="chatbox" ref={chatboxRef}>
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} />
      ))}
      
      {isLoading && (
        <div className="loading-message">
          <div className="loading-avatar">
            <img src="/public/Nagisa_avatar.jpg" alt="Nagisa" className="avatar" />
          </div>
          <div className="loading-content">
            <div className="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ChatBox // 默认导出ChatBox组件，一般用模块名。引入的时候可以不用加在{}中。