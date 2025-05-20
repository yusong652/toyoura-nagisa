import React, { useRef, useState, useEffect } from 'react'
import { useChat } from '../contexts/ChatContext'
import MessageItem from './MessageItem.tsx'
import './ChatBox.css'

const ChatBox: React.FC = () => {
  const { messages, sessions, currentSessionId } = useChat()
  const chatboxRef = useRef<HTMLDivElement>(null)
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)
  
  // 获取当前会话标题
  const currentSessionTitle = sessions.find(session => session.id === currentSessionId)?.name || '新会话'
  
  // 当点击chatbox空白区域时，清除选中状态
  const handleChatboxClick = (e: React.MouseEvent) => {
    // 确保点击的是chatbox自身而不是其子元素
    if (e.target === chatboxRef.current) {
      setSelectedMessageId(null);
    }
  };

  // Add automatic scrolling effect when messages change
  useEffect(() => {
    if (chatboxRef.current) {
      // Use smooth scrolling to bottom when new messages arrive
      chatboxRef.current.scrollTo({
        top: chatboxRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [messages]);

  // Add a MutationObserver to detect content changes and scroll down
  useEffect(() => {
    const chatboxElement = chatboxRef.current;
    if (!chatboxElement) return;

    const scrollToBottom = () => {
      chatboxElement.scrollTo({
        top: chatboxElement.scrollHeight,
        behavior: 'smooth'
      });
    };

    // Create a MutationObserver to watch for content changes
    const observer = new MutationObserver((mutations) => {
      // If there were character data changes or child list changes, scroll down
      if (mutations.some(mutation => 
          mutation.type === 'characterData' || 
          mutation.type === 'childList')) {
        scrollToBottom();
      }
    });

    // Start observing the chatbox with options
    observer.observe(chatboxElement, {
      childList: true,      // Watch for changes to child elements
      subtree: true,        // Watch the entire subtree
      characterData: true   // Watch for changes to text content
    });

    // Clean up the observer on component unmount
    return () => {
      observer.disconnect();
    };
  }, []);

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
          {/* Add scroll anchor element that will always be at the bottom */}
          <div className="scroll-anchor"></div>
        </div>
      </div>
    </>
  )
}

export default ChatBox