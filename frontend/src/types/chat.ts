export interface Message {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  files?: FileData[];
  timestamp: number;
  streaming?: boolean; // 标记是否正在流式显示文本
  status?: MessageStatus; // 用户消息状态
  isLoading?: boolean; // 标记是否为加载中的消息
  isRead?: boolean; // 标记用户消息是否已读
  newText?: string; // 新增的文本部分，用于流式显示
  onRenderComplete?: () => void; // 渲染完成的回调函数
  toolState?: MessageToolState;
}

// 消息状态枚举
export enum MessageStatus {
  SENDING = 'sending', // 正在发送
  SENT = 'sent',       // 已发送到后端
  READ = 'read',       // 后端已传给LLM API
  ERROR = 'error'      // 发送出错
}

// 消息中的工具状态
export interface MessageToolState {
  isUsingTool: boolean;
  toolNames?: string[]; // 工具名称数组，支持单个和多个工具
  action?: string;
  thinking?: string; // AI thinking content
}

export interface FileData {
  name: string;
  type: string;
  data: string; // Base64编码的文件数据
}

export interface ChatState {
  messages: Message[];
  isLoading: boolean;
}

export interface ChatContextType extends ChatState {
  sendMessage: (text: string, files?: FileData[]) => Promise<void>;
  clearChat: () => void;
  deleteMessage: (messageId: string) => Promise<void>;
  generateImage: (sessionId: string) => Promise<{ success: boolean; image_path?: string; error?: string }>;
  generateVideo: (sessionId: string, motionStyle?: string) => Promise<{ success: boolean; video_path?: string; error?: string }>;
  addVideoMessage: (videoPath: string, content?: string) => string;
} 