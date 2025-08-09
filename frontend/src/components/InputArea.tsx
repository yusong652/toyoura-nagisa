import React, { useState, useRef, useEffect } from 'react'
import { useChat } from '../contexts/chat/ChatContext'
import { FileData } from '../types/chat'
import './InputArea.css'
import { ToolsToggle } from './ToolsToggle'

const InputArea: React.FC = () => {
  const [message, setMessage] = useState('')
  const [files, setFiles] = useState<FileData[]>([])
  const { sendMessage, isLoading } = useChat()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // 自适应高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }, [message])

  const handleMessageChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value)
  }

  const handleSendMessage = async () => {
    if (message.trim() || files.length > 0) {
      const currentMessage = message
      const currentFiles = [...files]
      
      // 立即清空输入框和文件
      setMessage('')
      setFiles([])
      
      // 重置文本区域高度
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
      
      // 发送消息
      await sendMessage(currentMessage, currentFiles)
    }
  }

  const handleKeyPress = async (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      await handleSendMessage()
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files)
      Promise.all(
        newFiles.map(file => {
          return new Promise<FileData>((resolve) => {
            const reader = new FileReader()
            reader.onload = (e) => {
              resolve({
                name: file.name,
                type: file.type,
                data: e.target?.result as string
              })
            }
            reader.readAsDataURL(file)
          })
        })
      ).then(fileData => {
        setFiles(prevFiles => [...prevFiles, ...fileData])
      })
    }
  }

  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items) return

    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image') !== -1) {
        const file = items[i].getAsFile()
        if (file) {
          const reader = new FileReader()
          reader.onload = (e) => {
            const newFile: FileData = {
              name: file.name || `pasted-image-${Date.now()}.png`,
              type: file.type,
              data: e.target?.result as string
            }
            setFiles(prevFiles => [...prevFiles, newFile])
          }
          reader.readAsDataURL(file)
        }
        break
      }
    }
  }

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index))
  }

  return (
    <div className="input-area">
      {files.length > 0 && (
        <div className="file-preview-area">
          {files.map((file, index) => (
            <div key={index} className="file-thumb-box">
              <button className="file-thumb-del" onClick={() => removeFile(index)}>×</button>
              {file.type.startsWith('image/') ? (
                <img 
                  src={file.data} 
                  alt={file.name} 
                  className="file-thumb-img" 
                />
              ) : (
                <div className="file-thumb-other">
                  <span className="file-icon">📄</span>
                  <span className="file-name">{file.name}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      <div className="message-input-container">
        <div className="input-corner-buttons">
          <button 
            className="add-file-btn" 
            onClick={() => fileInputRef.current?.click()}
            title="添加文件"
            type="button"
          >
            <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" strokeWidth="2" fill="none">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
          </button>
          <ToolsToggle />
          <input
            type="file"
            ref={fileInputRef}
            className="file-input"
            onChange={handleFileSelect}
            multiple
            hidden
          />
        </div>
        <textarea
          ref={textareaRef}
          className="message-input with-corner-buttons"
          placeholder="输入消息..."
          value={message}
          onChange={handleMessageChange}
          onKeyPress={handleKeyPress}
          onPaste={handlePaste}
          disabled={isLoading}
        />
        <button 
          className="send-button" 
          onClick={handleSendMessage}
          disabled={isLoading || (message.trim() === '' && files.length === 0)}
          title="发送消息"
        >
          <svg viewBox="0 0 24 24" width="28" height="28" stroke="currentColor" strokeWidth="2" fill="none">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </div>
    </div>
  )
}

export default InputArea 