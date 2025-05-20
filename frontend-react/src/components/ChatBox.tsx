import React, { useEffect, useRef, useState } from 'react'
import { useChat } from '../contexts/ChatContext'
import MessageItem from './MessageItem.tsx'
import './ChatBox.css'

const ChatBox: React.FC = () => {
  const { messages, sessions, currentSessionId } = useChat()
  const chatboxRef = useRef<HTMLDivElement>(null)
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)
  const scrollLockRef = useRef(true) // 控制是否锁定滚动到底部

  // Get the current session title
  const currentSessionTitle = sessions.find(session => session.id === currentSessionId)?.name || '新会话'

  // 强制滚动到底部，不使用平滑滚动
  const forceScrollToBottom = () => {
    if (chatboxRef.current && scrollLockRef.current) {
      // 使用直接赋值而不是scrollTo，避免动画引起的问题
      chatboxRef.current.scrollTop = chatboxRef.current.scrollHeight;
    }
  };

  // 仅在消息列表变化时滚动到底部
  useEffect(() => {
    forceScrollToBottom();
    
    // 短暂延迟后再次滚动，处理可能的异步内容加载
    const timeoutId = setTimeout(() => {
      forceScrollToBottom();
    }, 100);
    
    return () => clearTimeout(timeoutId);
  }, [messages]);

  // 监听滚动事件，判断是否应该锁定滚动
  useEffect(() => {
    const chatbox = chatboxRef.current;
    if (!chatbox) return;
    
    const handleScroll = () => {
      if (!chatbox) return;
      
      // 如果用户位于底部附近，激活滚动锁定
      const isNearBottom = chatbox.scrollHeight - chatbox.scrollTop - chatbox.clientHeight < 50;
      scrollLockRef.current = isNearBottom;
    };
    
    chatbox.addEventListener('scroll', handleScroll);
    return () => chatbox.removeEventListener('scroll', handleScroll);
  }, []);
  
  // 当点击chatbox空白区域时，清除选中状态
  const handleChatboxClick = (e: React.MouseEvent) => {
    // 确保点击的是chatbox自身而不是其子元素
    if (e.target === chatboxRef.current) {
      setSelectedMessageId(null);
    }
  };

  return (
    <>
      <div className="chatbox-title-bar">
        <h2 className="chatbox-title">{currentSessionTitle}</h2>
      </div>
      <div className="chatbox-container">
        <div className="chatbox" ref={chatboxRef} onClick={handleChatboxClick}>
          {messages.map((message) => (
            <MessageItem 
              key={message.id} 
              message={message} 
              selectedMessageId={selectedMessageId}
              onMessageSelect={setSelectedMessageId}
            />
          ))}
          {/* 空白div，确保滚动条总是能到达真正的底部 */}
          <div style={{ height: '20px' }}></div>
        </div>
      </div>
    </>
  )
}

export default ChatBox // 默认导出ChatBox组件，一般用模块名。引入的时候可以不用加在{}中。