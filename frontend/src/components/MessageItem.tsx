import React, { useState, useEffect, useRef } from 'react'
import './MessageItem.css'
import { Message, MessageStatus } from '../types/chat'
import { useChat } from '../contexts/chat/ChatContext'
import MessageToolState from './MessageToolState'
import ImageViewer from './ImageViewer'
import ImageWithVideoAction from './ImageWithVideoAction'
import VideoPlayer from './VideoPlayer'
import UnifiedErrorDisplay from './UnifiedErrorDisplay'
import ReactMarkdown from 'react-markdown'
import { useImageNavigation } from '../hooks/useImageNavigation'
import { useErrorDisplay } from '../hooks/useErrorDisplay'
import { formatSmartTime } from '../utils/timeFormatter'

interface MessageItemProps {
  message: Message
  onMessageSelect: (id: string | null) => void
  selectedMessageId: string | null
  allMessages: Message[] // 新增：用于图片导航
}


const MessageItem: React.FC<MessageItemProps> = ({ message, onMessageSelect, selectedMessageId, allMessages }) => {
  const { sender, text, files, streaming, isLoading, status, id, toolState, newText, onRenderComplete } = message
  const [displayText, setDisplayText] = useState('')
  const [dotCount, setDotCount] = useState(0)
  const { deleteMessage } = useChat()
  const { error, showTemporaryError, clearError } = useErrorDisplay()
  const [viewerOpen, setViewerOpen] = useState(false)
  const [currentImageUrl, setCurrentImageUrl] = useState<string>('')
  const [showVideoPlayer, setShowVideoPlayer] = useState(false)
  const [currentVideoUrl, setCurrentVideoUrl] = useState<string>('')
  const [currentVideoFormat, setCurrentVideoFormat] = useState<string>('mp4')
  
  // Use image navigation hook
  const { allImages, getImageIndex } = useImageNavigation(allMessages)
  const [chunks, setChunks] = useState<string[]>([])
  
  // 检查当前消息是否被选中
  const isSelected = id && selectedMessageId === id
  
  // 处理文本更新
  useEffect(() => {
    if (streaming && sender === 'bot') {
      if (newText) {
        // 有newText时，增量更新
        setChunks(prev => [...prev, newText])
        setDisplayText(prev => prev + newText)
        // 调用渲染完成回调
        onRenderComplete?.()
      } else if (text) {
        // 没有newText但有text（TTS关闭时的情况）
        // 使用函数式更新避免依赖displayText
        setDisplayText(prev => {
          // 只在text实际变化时更新
          if (prev !== text) {
            // 设置一个虚拟chunk以避免显示loading
            setChunks(current => current.length === 0 ? [''] : current)
            return text
          }
          return prev
        })
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
      showTemporaryError('Failed to delete message. Please try again.', 4000)
    }
  }
  
  // Format timestamp with smart time display
  const getFormattedTime = (timestamp: number) => {
    return formatSmartTime(timestamp, { showRelative: true })
  }
  
  // 为流式文本添加渐变效果
  const renderStreamingText = () => {
    // 如果有工具状态和action，显示action text
    const textToDisplay = (toolState?.isUsingTool && toolState?.action) 
      ? toolState.action 
      : displayText;
    
    if (!streaming || sender !== 'bot') {
      return textToDisplay ? (
        <div className="message-text">
          <ReactMarkdown>{textToDisplay}</ReactMarkdown>
        </div>
      ) : null
    }
    
    // 流式渲染，使用完整文本进行渲染，但保持块级淡入效果
    const renderedText = textToDisplay
    const lastChunkStart = renderedText.length - (chunks[chunks.length - 1]?.length || 0)
    
    return renderedText ? (
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
    ) : null
  }
  
  // 渲染消息状态
  const renderMessageStatus = () => {
    // 对用户消息强制设置状态
    if (sender !== 'user') return null;
    
    let statusText = '';
    let statusClass = '';
    
    if (status === MessageStatus.SENDING) {
      statusText = 'Sending';
      statusClass = 'status-sending';
    } else if (status === MessageStatus.SENT) {
      statusText = 'Sent';
      statusClass = 'status-sent';
    } else if (status === MessageStatus.READ) {
      statusText = 'Read';
      statusClass = 'status-read';
    } else if (status === MessageStatus.ERROR) {
      statusText = 'Failed';
      statusClass = 'status-error';
    } else {
      // No status info messages (like history messages) default to read
      statusText = 'Read';
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
      tooltip.textContent = 'Toyoura Nagisa\nPersonality: Energetic, cute, clingy\nHobbies: Chatting with you, being adorable\nBio: Nagisa is your AI virtual companion who loves to keep you company and interact with you!'
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
    setCurrentImageUrl(imageUrl);
    setViewerOpen(true);
  };

  const handleVideoClick = (videoUrl: string, format: string = 'mp4') => {
    setCurrentVideoUrl(videoUrl);
    setCurrentVideoFormat(format);
    setShowVideoPlayer(true);
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
            {(renderStreamingText() || (files && files.length > 0 && !isLoading)) && (
              <div className="message-content">
                {displayText && renderStreamingText()}
                
                {files && files.length > 0 && !isLoading && (() => {
                      
                  return (
                    <div className="message-files">
                      {files.map((file, index) => (
                        <div key={index} className="file-preview">
                          {file.type.startsWith('image/') ? (
                            <div style={{ position: 'relative', display: 'inline-block' }}>
                              <img 
                                src={file.data} 
                                alt={file.name} 
                                className="file-image" 
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleImageClick(file.data);
                                }}
                              />
                              {sender === 'bot' && (
                                <ImageWithVideoAction />
                              )}
                            </div>
                          ) : file.type.startsWith('video/') || file.name.toLowerCase().endsWith('.mp4') || file.name.toLowerCase().endsWith('.gif') || file.name.toLowerCase().endsWith('.webm') ? (
                            (() => {
                              const fileName = file.name.toLowerCase();
                              let format = 'mp4'; // 默认
                              if (fileName.endsWith('.gif')) {
                                format = 'gif';
                              } else if (fileName.endsWith('.webm')) {
                                format = 'webm';
                              } else if (fileName.endsWith('.mp4')) {
                                format = 'mp4';
                              }
                              
                              return (
                                <div 
                                  className="file-video-preview elegant-video" 
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleVideoClick(file.data, format);
                                  }}
                                >
                                  <video 
                                    src={file.data} 
                                    className="elegant-video-thumbnail"
                                    muted
                                    preload="metadata"
                                  />
                                  <div className="elegant-video-overlay">
                                    <div className="elegant-play-button">
                                      <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
                                        <path d="M8 5v14l11-7z"/>
                                      </svg>
                                    </div>
                                  </div>
                                  <div className="elegant-video-info">
                                    <div className="video-format-badge">
                                      {format.toUpperCase()}
                                    </div>
                                  </div>
                                </div>
                              );
                            })()
                          ) : (
                            <div className="file-info">
                              <span className="file-name">{file.name}</span>
                              <span className="file-size">{(file.data.length / 1024).toFixed(1)} KB</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  );
                })()}
              <span 
                className="message-time" 
                title={getFormattedTime(message.timestamp).fullTime}
              >
                {getFormattedTime(message.timestamp).display}
              </span>
            </div>
            )}
          </div>
        ) : (
          <div className="message-content">
            {renderStreamingText()}
            
            {files && files.length > 0 && !isLoading && (() => {
              
              return (
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
                          <span className="file-icon">📄</span>
                          <span className="file-name">{file.name}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              );
            })()}
            <span 
              className="message-time" 
              title={getFormattedTime(message.timestamp).fullTime}
            >
              {getFormattedTime(message.timestamp).display}
            </span>
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
      {viewerOpen && currentImageUrl && allImages.length > 0 && (
        <ImageViewer
          open={viewerOpen}
          onClose={() => setViewerOpen(false)}
          images={allImages.map(img => img.url)}
          initialIndex={getImageIndex(currentImageUrl)}
          imageNames={allImages.map(img => img.name)}
        />
      )}
      {showVideoPlayer && currentVideoUrl && (
        <VideoPlayer
          videoUrl={currentVideoUrl}
          format={currentVideoFormat}
          onClose={() => setShowVideoPlayer(false)}
        />
      )}
      <UnifiedErrorDisplay
        error={error}
        onClose={clearError}
      />
    </>
  )
}

export default MessageItem