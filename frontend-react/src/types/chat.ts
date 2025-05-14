export interface Message {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  files?: FileData[];
  timestamp: number;
  streaming?: boolean; // 标记是否正在流式显示文本
  isLoading?: boolean; // 标记是否为加载中的消息
  isRead?: boolean; // 标记用户消息是否已读
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

export interface ChatState {
  messages: Message[];
  isLoading: boolean;
  loadingMessageId: string | null;
  sessions: ChatSession[];
  currentSessionId: string | null;
}

export interface ChatContextType extends ChatState {
  sendMessage: (text: string, files?: FileData[]) => Promise<void>;
  clearChat: () => void;
  createNewSession: (name?: string) => Promise<string>;
  switchSession: (sessionId: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  refreshSessions: () => Promise<void>;
} 