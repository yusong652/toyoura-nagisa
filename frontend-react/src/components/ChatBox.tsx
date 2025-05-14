import React, { useEffect, useRef, useState } from 'react'
import { useChat } from '../contexts/ChatContext'
import MessageItem from './MessageItem.tsx'
import './ChatBox.css'

const ChatBox: React.FC = () => {
  const { messages } = useChat()
  const chatboxRef = useRef<HTMLDivElement>(null)
  
  // 滚动到底部
  useEffect(() => {
    if (chatboxRef.current) {
      chatboxRef.current.scrollTop = chatboxRef.current.scrollHeight
    }
  }, [messages])

  return (
    <div className="chatbox" ref={chatboxRef}>
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} />
      ))}
    </div>
  )
}

export default ChatBox // 默认导出ChatBox组件，一般用模块名。引入的时候可以不用加在{}中。