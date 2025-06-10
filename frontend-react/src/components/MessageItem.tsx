import React, { useState, useEffect, useRef } from 'react'
import './MessageItem.css'
import { Message, MessageStatus } from '../types/chat'
import { useChat } from '../contexts/ChatContext'
import MessageToolState from './MessageToolState'

interface MessageItemProps {
  message: Message
  onMessageSelect: (id: string | null) => void
  selectedMessageId: string | null
}

const MessageItem: React.FC<MessageItemProps> = ({ message, onMessageSelect, selectedMessageId }) => {
  const { sender, text, files, streaming, isLoading, status, timestamp, id, toolState } = message
  const [displayText, setDisplayText] = useState('')
  const [dotCount, setDotCount] = useState(0)
  const textRef = useRef(text)
  const charIndexRef = useRef(0)
  const { deleteMessage } = useChat()
  
  // 检查当前消息是否被选中
  const isSelected = id && selectedMessageId === id
  
  // 动态点号效果
  useEffect(() => {
    if (!isLoading) return
    
    const interval = setInterval(() => {
      setDotCount(prev => (prev + 1) % 4)
    }, 500)
    
    return () => clearInterval(interval)
  }, [isLoading])
  
  // 流式显示文本
  useEffect(() => {
    // 如果是加载中的消息，不处理文本
    if (isLoading) return
    
    // 仅对机器人消息且标记为流式显示的消息应用效果
    if (sender !== 'bot' || !streaming) {
      setDisplayText(text)
      return
    }
    
    // 如果文本发生变化，更新引用并重置字符索引
    if (textRef.current !== text) {
      textRef.current = text
      // 只显示到当前索引，保留已显示的部分
      const currentDisplayLength = Math.min(charIndexRef.current, text.length)
      setDisplayText(text.substring(0, currentDisplayLength))
    }
    
    // 如果还有字符未显示，继续显示
    if (charIndexRef.current < text.length) {
      const interval = setInterval(() => {
        if (charIndexRef.current < text.length) {
          // 每次增加1个字符
          charIndexRef.current += 1
          setDisplayText(text.substring(0, charIndexRef.current))
        } else {
          clearInterval(interval)
        }
      }, 30) // 每30毫秒显示多个字符，比之前更快
      
      return () => clearInterval(interval)
    }
  }, [sender, text, streaming, isLoading])
  
  // 处理消息点击
  const handleMessageClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!id) return;
    
    // 如果当前消息已被选中，则取消选中；否则选中当前消息
    if (isSelected) {
      onMessageSelect(null);
    } else {
      onMessageSelect(id);
    }
  }
  
  // 处理删除消息
  const handleDeleteMessage = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!id) return
    
    try {
      await deleteMessage(id)
      // 删除后清除选中状态
      onMessageSelect(null)
    } catch (error) {
      console.error('删除消息失败:', error)
      // 可以在这里添加错误提示
    }
  }
  
  // 格式化时间戳
  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp)
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }
  
  // 为流式文本添加渐变效果
  const renderStreamingText = () => {
    // 如果是加载中的消息，显示加载指示器
    if (isLoading) {
      return (
        <div className="typing-container">
          <div className="loading-spinner"></div>
          <div className="typing-text">正在输入{'.'.repeat(dotCount)}</div>
        </div>
      )
    }
    
    if (!streaming || sender !== 'bot') {
      // 替换为一致的换行符处理方式，确保非流式渲染也正确显示换行
      const textWithBreaks = displayText.split('\n').map((line, i) => (
        <React.Fragment key={i}>
          {line}
          {i < displayText.split('\n').length - 1 && <br />}
        </React.Fragment>
      ));
      return <div className="message-text">{textWithBreaks}</div>;
    }
    
    // 将文本按换行符拆分，保留空行
    const lines = displayText.split('\n');
    
    return (
      <div className="message-text streaming-text">
        {lines.map((line, lineIndex) => (
          <React.Fragment key={`line-${lineIndex}`}>
            {/* 渲染每个字符，添加渐变效果 */}
            {line.split('').map((char, charIndex) => (
              <span 
                key={`${lineIndex}-${charIndex}`} 
                className="fade-in-char"
                style={{ 
                  animationDelay: '0ms',
                }}
              >
                {char}
              </span>
            ))}
            {/* 在每行后添加换行，除了最后一行 */}
            {lineIndex < lines.length - 1 && <br />}
          </React.Fragment>
        ))}
      </div>
    )
  }
  
  // 渲染消息状态
  const renderMessageStatus = () => {
    // 对用户消息强制设置状态
    if (sender !== 'user') return null;
    
    let statusText = '';
    let statusClass = '';
    
    if (status === MessageStatus.SENDING) {
      statusText = '发送中';
      statusClass = 'status-sending';
    } else if (status === MessageStatus.SENT) {
      statusText = '已发送';
      statusClass = 'status-sent';
    } else if (status === MessageStatus.READ) {
      statusText = '已读';
      statusClass = 'status-read';
    } else if (status === MessageStatus.ERROR) {
      statusText = '发送失败';
      statusClass = 'status-error';
    } else {
      // 没有状态信息的消息（如历史消息）默认显示为已读
      statusText = '已读';
      statusClass = 'status-read';
    }
    
    return (
      <div className={`message-status ${statusClass}`}>
        {statusText}
      </div>
    );
  }
  
  // 头像悬停显示信息
  const handleMouseEnter = (e: React.MouseEvent<HTMLImageElement>) => {
    const tooltip = document.createElement('div')
    tooltip.className = 'avatar-tooltip'
    
    if (sender === 'user') {
      tooltip.textContent = 'User\nName：yusong\nIntroduction： developer of aiNagisa.'
    } else {
      tooltip.textContent = 'Toyoura Nagisa\n性格：元气、可爱、黏人\n爱好：和你聊天、卖萌撒娇\n简介：Nagisa是你的AI虚拟伙伴，喜欢陪伴你、和你互动！'
    }
    
    document.body.appendChild(tooltip)
    const rect = e.currentTarget.getBoundingClientRect()
    
    if (sender === 'user') {
      tooltip.style.left = `${rect.left - tooltip.offsetWidth - 10}px`
      tooltip.style.top = `${rect.top - 10}px`
    } else {
      tooltip.style.left = `${rect.right + 10}px`
      tooltip.style.top = `${rect.top - 10}px`
    }
  }
  
  const handleMouseLeave = () => {
    const tooltip = document.querySelector('.avatar-tooltip')
    if (tooltip) tooltip.remove()
  }

  return (
    <div 
      className={`message ${sender} ${isSelected ? 'selected' : ''}`}
      onClick={handleMessageClick}
    >
      <img 
        src={sender === 'user' ? '/user-avatar.jpg' : '/Nagisa_avatar.jpg'} 
        alt={sender === 'user' ? 'User' : 'Nagisa'} 
        className="avatar"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      />
      
      {sender === 'bot' ? (
        <div className="message-wrapper">
          {toolState && <MessageToolState toolState={toolState} />}
          <div className="message-content">
            {renderStreamingText()}
            
            {files && files.length > 0 && !isLoading && (
              <div className="message-files">
                {files.map((file, index) => (
                  <div key={index} className="file-preview">
                    {file.type.startsWith('image/') ? (
                      <img src={file.data} alt={file.name} className="file-image" />
                    ) : (
                      <div className="file-info">
                        <span className="file-icon">📄</span>
                        <span className="file-name">{file.name}</span>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
          
          {!streaming && !isLoading && (
            <div className="message-time">
              {formatTime(timestamp)}
            </div>
          )}
        </div>
      ) : (
        <div className="message-content">
          {renderStreamingText()}
          
          {files && files.length > 0 && !isLoading && (
            <div className="message-files">
              {files.map((file, index) => (
                <div key={index} className="file-preview">
                  {file.type.startsWith('image/') ? (
                    <img src={file.data} alt={file.name} className="file-image" />
                  ) : (
                    <div className="file-info">
                      <span className="file-icon">📄</span>
                      <span className="file-name">{file.name}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      
      {/* 显示消息状态 */}
      {renderMessageStatus()}
      
      {/* 删除按钮 - 仅在消息被选中时显示 */}
      {isSelected && id && !isLoading && !streaming && (
        <div className="message-delete-button" onClick={handleDeleteMessage}>
          <svg width="12" height="12" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M2 2L12 12M2 12L12 2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      )}
    </div>
  )
}

export default MessageItem