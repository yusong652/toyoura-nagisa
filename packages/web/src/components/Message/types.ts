import { Message, MessageStatus, MessageRole } from '@toyoura-nagisa/core'
import { VideoFormat } from '../VideoPlayer/types'

// 基础消息属性
export interface BaseMessageProps {
  message: Message
  isSelected: boolean
  onMessageClick: (e: React.MouseEvent) => void
}

// 用户消息渲染器属性
export interface UserMessageRendererProps extends BaseMessageProps {
  onImageClick: (imageUrl: string) => void
}

// 机器人消息渲染器属性
export interface BotMessageRendererProps extends BaseMessageProps {
  onImageClick: (imageUrl: string) => void
  onVideoClick: (videoUrl: string, format?: VideoFormat) => void
}

// 消息文本组件属性
export interface MessageTextProps {
  content: string
  className?: string
}

// 流式文本渲染器属性
export interface StreamingTextRendererProps {
  displayText: string
  chunks: string[]
  streaming: boolean
  isLoading: boolean
  className?: string
}

// 消息文件组件属性
export interface MessageFilesProps {
  files: any[]
  isLoading: boolean
  onImageClick: (imageUrl: string) => void
  onVideoClick?: (videoUrl: string, format?: VideoFormat) => void
  role: MessageRole
}

// 文件预览组件属性
export interface FilePreviewProps {
  file: {
    name: string
    type: string
    data: string
  }
  onImageClick?: (imageUrl: string) => void
  onVideoClick?: (videoUrl: string, format?: VideoFormat) => void
  role: MessageRole
}

// 消息状态组件属性
export interface MessageStatusProps {
  status?: MessageStatus
  role: MessageRole
}

// 消息时间戳组件属性
export interface MessageTimestampProps {
  timestamp: number
  className?: string
}

// 消息头像组件属性
export interface MessageAvatarProps {
  role: MessageRole
  onMouseEnter?: (e: React.MouseEvent<HTMLImageElement>) => void
  onMouseLeave?: () => void
}

// 消息操作组件属性
export interface MessageActionsProps {
  messageId?: string
  isSelected: boolean
  isLoading?: boolean
  streaming?: boolean
  onDelete: (e: React.MouseEvent) => void
}


// 消息事件处理器类型
export interface MessageEventHandlers {
  onMessageClick: (e: React.MouseEvent) => void
  onDeleteMessage: (e: React.MouseEvent) => void
  onImageClick: (imageUrl: string) => void
  onVideoClick: (videoUrl: string, format?: VideoFormat) => void
}

// 消息状态 Hook 返回类型
export interface MessageStateHookReturn {
  displayText: string
  chunks: string[]
  dotCount: number
  isSelected: boolean
}

// 流式文本 Hook 返回类型
export interface StreamingTextHookReturn {
  displayText: string
  chunks: string[]
  setDisplayText: React.Dispatch<React.SetStateAction<string>>
  setChunks: React.Dispatch<React.SetStateAction<string[]>>
}