import React, { useState, useEffect, useRef } from 'react'
import './MessageItem.css'
import { Message } from '../types/chat'

interface MessageItemProps {
  message: Message
}

const MessageItem: React.FC<MessageItemProps> = ({ message }) => {
  const { sender, text, files, streaming } = message
  const [displayText, setDisplayText] = useState('')
  const textRef = useRef(text)
  const charIndexRef = useRef(0)
  
  // 流式显示文本
  useEffect(() => {
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
          // 每次增加2个字符，但不超过文本长度
          charIndexRef.current = Math.min(charIndexRef.current + 2, text.length)
          setDisplayText(text.substring(0, charIndexRef.current))
        } else {
          clearInterval(interval)
        }
      }, 100) // 每100毫秒显示两个字符
      
      return () => clearInterval(interval)
    }
  }, [sender, text, streaming])
  
  // 为流式文本添加渐变效果
  const renderStreamingText = () => {
    if (!streaming || sender !== 'bot') {
      return <div className="message-text" dangerouslySetInnerHTML={{ __html: displayText }} />
    }
    
    // 将文本拆分为两个字符一组，并为每组添加渐变效果
    const textChunks: string[] = []
    for (let i = 0; i < displayText.length; i += 2) {
      if (i + 1 < displayText.length) {
        textChunks.push(displayText.substring(i, i + 2))
      } else {
        textChunks.push(displayText.substring(i, i + 1))
      }
    }
    
    return (
      <div className="message-text streaming-text">
        {textChunks.map((chunk, index) => (
          <span 
            key={index} 
            className="fade-in-char"
            style={{ 
              animationDelay: '0ms',
            }}
          >
            {chunk.split('').map((char, charIndex) => 
              char === '\n' ? <br key={`br-${index}-${charIndex}`} /> : char
            )}
          </span>
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
      
      <div className="message-content">
        {renderStreamingText()}
        
        {files && files.length > 0 && (
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
    </div>
  )
}

export default MessageItem 