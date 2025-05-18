import React, { useEffect, useRef, useState } from 'react'
import { useChat } from '../contexts/ChatContext'
import MessageItem from './MessageItem.tsx'
import './ChatBox.css'

const ChatBox: React.FC = () => {
  const { messages } = useChat()
  const chatboxRef = useRef<HTMLDivElement>(null)
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)

  // 滚动到底部
  useEffect(() => {
    if (chatboxRef.current) {
      chatboxRef.current.scrollTop = chatboxRef.current.scrollHeight
    }
  }, [messages])
  
  // 当点击chatbox空白区域时，清除选中状态
  const handleChatboxClick = (e: React.MouseEvent) => {
    // 确保点击的是chatbox自身而不是其子元素
    if (e.target === chatboxRef.current) {
      setSelectedMessageId(null);
    }
  };

  return (
    <div className="chatbox" ref={chatboxRef} onClick={handleChatboxClick}>
      {messages.map((message) => (
        <MessageItem 
          key={message.id} 
          message={message} 
          selectedMessageId={selectedMessageId}
          onMessageSelect={setSelectedMessageId}
        />
      ))}
    </div>
  )
}

export default ChatBox // 默认导出ChatBox组件，一般用模块名。引入的时候可以不用加在{}中。