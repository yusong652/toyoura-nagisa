import React, { useState, useEffect, useRef } from 'react'
import './MessageItem.css'
import { Message } from '../types/chat'

interface MessageItemProps {
  message: Message
}

const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const { sender, text, files, streaming, isLoading, isRead, timestamp } = message
  const [displayText, setDisplayText] = useState('')
  const [dotCount, setDotCount] = useState(0)
  const [showReadReceipt, setShowReadReceipt] = useState(false)
  const textRef = useRef(text)
  const charIndexRef = useRef(0)
  
  // 动态点号效果
  useEffect(() => {
    if (!isLoading) return
    
    const interval = setInterval(() => {
      setDotCount(prev => (prev + 1) % 4)
    }, 500)
    
    return () => clearInterval(interval)
  }, [isLoading])
  
  // 处理已读回执显示
  useEffect(() => {
    if (sender === 'user' && isRead) {
      setShowReadReceipt(true)
    }
  }, [sender, isRead])
  
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
    
    // 将文本拆分成行，确保每行正确显示，并且字符有渐变效果
    return (
      <div className="message-text streaming-text">
        {displayText.split('\n').map((line, lineIndex) => (
          <React.Fragment key={`line-${lineIndex}`}>
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
            {lineIndex < displayText.split('\n').length - 1 && <br />}
          </React.Fragment>
        ))}
      </div>
    )
  }
  
  // 头像悬停显示信息
  const handleMouseEnter = (e: React.MouseEvent<HTMLImageElement>) => {
    const tooltip = document.createElement('div')
    tooltip.className = 'avatar-tooltip'
    
    if (sender === 'user') {
      tooltip.textContent = 'User\n昵称：你自己\n简介：这是你在本聊天中的形象，可以自定义头像和昵称哦~'
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
    <div className={`message ${sender}`}>
      <img 
        src={sender === 'user' ? '/user-avatar.jpg' : '/Nagisa_avatar.jpg'} 
        alt={sender === 'user' ? 'User' : 'Nagisa'} 
        className="avatar"
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
      />
      
      {sender === 'bot' ? (
        <div className="message-wrapper">
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
      
      {sender === 'user' && isRead && (
        <div className={`read-receipt ${showReadReceipt ? 'visible' : ''}`}>
          已读
        </div>
      )}
    </div>
  )
}

export default MessageItem