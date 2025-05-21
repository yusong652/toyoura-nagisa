import React, { useRef, useState, useEffect } from 'react'
import { useChat } from '../contexts/ChatContext'
import MessageItem from './MessageItem.tsx'
import './ChatBox.css'

const ChatBox: React.FC = () => {
  const { messages, sessions, currentSessionId } = useChat()
  const chatboxRef = useRef<HTMLDivElement>(null)
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)
  const prevLastMessageId = useRef(messages[messages.length - 1]?.id);
  
  // 获取当前会话标题
  const currentSessionTitle = sessions.find(session => session.id === currentSessionId)?.name || '新会话'
  
  // 当点击chatbox空白区域时，清除选中状态
  const handleChatboxClick = (e: React.MouseEvent) => {
    // 确保点击的是chatbox自身而不是其子元素
    if (e.target === chatboxRef.current) {
      setSelectedMessageId(null);
    }
  };

  // 只在最后一条消息id变化时自动滚动到底部
  useEffect(() => {
    const lastMessageId = messages[messages.length - 1]?.id;
    if (lastMessageId && lastMessageId !== prevLastMessageId.current) {
      if (chatboxRef.current) {
        chatboxRef.current.scrollTo({
          top: chatboxRef.current.scrollHeight,
          behavior: 'smooth'
        });
      }
    }
    prevLastMessageId.current = lastMessageId;
  }, [messages]);

  return (
    <>
      <div className="chatbox-title-bar">
        <h2 className="chatbox-title">{currentSessionTitle}</h2>
      </div>
      <div className="chatbox-container">
        {/* 添加固定的顶部阴影 */}
        <div className="chatbox-top-shadow"></div>
        
        <div className="chatbox" ref={chatboxRef} onClick={handleChatboxClick}>
          {messages.map((message) => (
            <MessageItem 
              key={message.id} 
              message={message} 
              selectedMessageId={selectedMessageId}
              onMessageSelect={setSelectedMessageId}
            />
          ))}
          {/* Add scroll anchor element that will always be at the bottom */}
          <div className="scroll-anchor"></div>
        </div>
        
        {/* 添加固定的底部阴影 */}
        <div className="chatbox-bottom-shadow"></div>
      </div>
    </>
  )
}

export default ChatBox