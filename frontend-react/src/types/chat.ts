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
}

// 消息状态枚举
export enum MessageStatus {
  SENDING = 'sending', // 正在发送
  SENT = 'sent',       // 已发送到后端
  READ = 'read',       // 后端已传给LLM API
  ERROR = 'error'      // 发送出错
}

export interface FileData {
  name: string;
  type: string;
  data: string; // Base64编码的文件数据
}

export interface ChatSession {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export enum ConnectionStatus {
  CONNECTED = 'connected',
  CONNECTING = 'connecting',
  DISCONNECTED = 'disconnected',
  ERROR = 'error'
}

export interface ChatState {
  messages: Message[];
  isLoading: boolean;
  sessions: ChatSession[];
  currentSessionId: string | null;
  connectionStatus: ConnectionStatus;
  connectionError: string | null;
}

export interface ChatContextType extends ChatState {
  sendMessage: (text: string, files?: FileData[]) => Promise<void>;
  clearChat: () => void;
  createNewSession: (name?: string) => Promise<string>;
  switchSession: (sessionId: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  deleteMessage: (messageId: string) => Promise<void>;
  refreshSessions: () => Promise<void>;
  checkConnection: () => Promise<boolean>;
} 