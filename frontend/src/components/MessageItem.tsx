import React, { useState, useEffect, useRef } from 'react'
import './MessageItem.css'
import { Message, MessageStatus } from '../types/chat'
import { useChat } from '../contexts/chat/ChatContext'
import MessageToolState from './MessageToolState'
import ImagePreview from './ImagePreview'
import ReactMarkdown from 'react-markdown'

interface MessageItemProps {
  message: Message
  onMessageSelect: (id: string | null) => void
  selectedMessageId: string | null
}

interface FileData {
  type: string
  data: string
  name: string
}

interface ToolState {
  // Add appropriate properties for ToolState
}

const MessageItem: React.FC<MessageItemProps> = ({ message, onMessageSelect, selectedMessageId }) => {
  const { sender, text, files, streaming, isLoading, status, id, toolState, newText, onRenderComplete } = message
  const [displayText, setDisplayText] = useState('')
  const [dotCount, setDotCount] = useState(0)
  const textRef = useRef(text)
  const charIndexRef = useRef(0)
  const { deleteMessage } = useChat()
  const [previewImage, setPreviewImage] = useState<string | null>(null)
  const [chunks, setChunks] = useState<string[]>([])
  
  // 检查当前消息是否被选中
  const isSelected = id && selectedMessageId === id
  
  // 处理文本更新
  useEffect(() => {
    if (streaming && sender === 'bot') {
      if (newText) {
        // 添加新的文本块，同时更新完整文本
        setChunks(prev => [...prev, newText])
        setDisplayText(prev => prev + newText)
        // 调用渲染完成回调
        onRenderComplete?.()
      }
    } else {
      // 非流式情况，直接设置文本
      setDisplayText(text || '')
      setChunks([])
    }
  }, [text, newText, streaming, sender, onRenderComplete])

  // 处理加载动画
  useEffect(() => {
    let timer: number
    if (isLoading || (streaming && sender === 'bot' && chunks.length === 0)) {
      timer = window.setInterval(() => {
        setDotCount(prev => (prev % 3) + 1)
      }, 500)
    }
    return () => {
      if (timer) {
        window.clearInterval(timer)
      }
    }
  }, [isLoading, streaming, sender, chunks.length])
  
  // 处理消息点击
  const handleMessageClick = (e: React.MouseEvent) => {
    // 如果点击的是图片，不触发消息选中
    if ((e.target as HTMLElement).closest('.file-image')) {
      return;
    }
    onMessageSelect(isSelected ? null : message.id);
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
    if (!streaming || sender !== 'bot') {
      return (
        <div className="message-text">
          <ReactMarkdown>{displayText}</ReactMarkdown>
        </div>
      )
    }
    
    // 流式渲染，使用完整文本进行渲染，但保持块级淡入效果
    const renderedText = displayText
    const lastChunkStart = renderedText.length - (chunks[chunks.length - 1]?.length || 0)
    
    return (
      <div className="message-text streaming-text">
        {/* 渲染已完成的部分 */}
        {lastChunkStart > 0 && (
          <div className="completed-text">
            <ReactMarkdown>{renderedText.slice(0, lastChunkStart)}</ReactMarkdown>
          </div>
        )}
        {/* 渲染最新的块 */}
        {chunks.length > 0 && (
          <div key={`chunk-${chunks.length}`} className="fade-in-chunk">
            <ReactMarkdown>{renderedText.slice(lastChunkStart)}</ReactMarkdown>
          </div>
        )}
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

  const handleImageClick = (imageUrl: string) => {
    setPreviewImage(imageUrl);
  };

  return (
    <>
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
                        <img 
                          src={file.data} 
                          alt={file.name} 
                          className="file-image" 
                          onClick={(e) => {
                            e.stopPropagation();
                            handleImageClick(file.data);
                          }}
                        />
                      ) : (
                        <div className="file-info">
                          <span className="file-name">{file.name}</span>
                          <span className="file-size">{(file.data.length / 1024).toFixed(1)} KB</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <span className="message-time">{formatTime(message.timestamp)}</span>
            </div>
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
            <span className="message-time">{formatTime(message.timestamp)}</span>
          </div>
        )}
        
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
      {previewImage && (
        <ImagePreview
          open={true}
          onClose={() => setPreviewImage(null)}
          imageUrl={previewImage}
        />
      )}
    </>
  )
}

export default MessageItem