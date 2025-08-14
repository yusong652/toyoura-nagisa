import React, { useRef, useState, useEffect } from 'react'
import { useChat } from '../contexts/chat/ChatContext'
import { useSession } from '../contexts/session/SessionContext'
import MessageItem from './MessageItem.tsx'
import './ChatBox.css'
import GenerateImageButton from './GenerateImageButton'

const ChatBox: React.FC = () => {
  const { messages } = useChat()
  const { sessions, currentSessionId, refreshTitle } = useSession()
  const chatboxRef = useRef<HTMLDivElement>(null)
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)
  const prevLastMessageId = useRef(messages[messages.length - 1]?.id);
  const [isRefreshingTitle, setIsRefreshingTitle] = useState(false);
  
  // 获取当前会话标题
  const currentSessionTitle = sessions.find(session => session.id === currentSessionId)?.name || 'New Chat'
  
  // 判断是否有足够的消息来生成标题
  const hasEnoughMessages = messages.length >= 2;
  const hasUserAndBotMessages = messages.some(msg => msg.sender === 'user') && 
                                 messages.some(msg => msg.sender === 'bot');
  const canRefreshTitle = hasEnoughMessages && hasUserAndBotMessages;
  
  // 当点击chatbox空白区域时，清除选中状态
  const handleChatboxClick = (e: React.MouseEvent) => {
    // 确保点击的是chatbox自身而不是其子元素
    if (e.target === chatboxRef.current) {
      setSelectedMessageId(null);
    }
  };

  // 处理刷新标题的点击
  const handleRefreshTitle = async () => {
    if (!currentSessionId || isRefreshingTitle || !canRefreshTitle) return;
    
    try {
      setIsRefreshingTitle(true);
      await refreshTitle(currentSessionId);
    } catch (error) {
      console.error('刷新标题失败:', error);
      // 可以在这里添加错误提示
    } finally {
      setIsRefreshingTitle(false);
    }
  };

  // 添加自动滚动功能
  useEffect(() => {
    if (chatboxRef.current) {
      const chatBox = chatboxRef.current;
      const shouldAutoScroll = 
        // 当新消息添加时
        chatBox.scrollHeight - chatBox.scrollTop <= chatBox.clientHeight + 100 ||
        // 当正在流式输出时
        messages.some(msg => msg.streaming);
      
      if (shouldAutoScroll) {
        // 计算滚动位置，留出 20% 的空间在底部
        const scrollPosition = chatBox.scrollHeight - chatBox.clientHeight * 0.8;
        chatBox.scrollTo({
          top: scrollPosition,
          behavior: 'smooth'
        });
      }
    }
  }, [messages]);

  // 只在最后一条消息id变化时自动滚动到底部
  useEffect(() => {
    const lastMessageId = messages[messages.length - 1]?.id;
    if (lastMessageId && lastMessageId !== prevLastMessageId.current) {
      if (chatboxRef.current) {
        const chatBox = chatboxRef.current;
        // 计算滚动位置，留出 20% 的空间在底部
        const scrollPosition = chatBox.scrollHeight - chatBox.clientHeight * 0.8;
        chatBox.scrollTo({
          top: scrollPosition,
          behavior: 'smooth'
        });
      }
    }
    prevLastMessageId.current = lastMessageId;
  }, [messages]);

  return (
    <>
      <div className="chatbox-title-bar">
        <h2 className="chatbox-title">
          {currentSessionTitle}
          {currentSessionId && (
            <button 
              className={`refresh-title-button ${isRefreshingTitle ? 'loading' : ''} ${!canRefreshTitle ? 'disabled' : ''}`}
              onClick={handleRefreshTitle}
              disabled={isRefreshingTitle || !canRefreshTitle}
              title={canRefreshTitle ? "Refresh Title" : "Need at least one user message and one AI reply to refresh title"}
              aria-label="Refresh Title"
            >
              {isRefreshingTitle ? (
                // 加载中图标
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"></circle>
                  <path d="M12 6v6l4 2"></path>
                </svg>
              ) : (
                // 刷新图标
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 2v6h-6"></path>
                  <path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path>
                  <path d="M3 22v-6h6"></path>
                  <path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path>
                </svg>
              )}
            </button>
          )}
        </h2>
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
        <div className="chatbox-controls">
          <GenerateImageButton />
        </div>
        {/* 添加固定的底部阴影 */}
        <div className="chatbox-bottom-shadow"></div>
      </div>
    </>
  )
}

export default ChatBox