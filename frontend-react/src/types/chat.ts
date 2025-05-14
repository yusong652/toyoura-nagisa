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

export interface ChatState {
  messages: Message[];
  isLoading: boolean;
  loadingMessageId: string | null;
}

export interface ChatContextType extends ChatState {
  sendMessage: (text: string, files?: FileData[]) => Promise<void>;
  clearChat: () => void;
} 