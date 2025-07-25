import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect, useRef } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message, FileData, ChatContextType, ChatSession, ConnectionStatus, MessageStatus } from '../types/chat'
import { useAudio } from './AudioContext.tsx'
import { playMotion } from '../utils/live2d'
import GeolocationService from '../utils/geolocation'

const ChatContext = createContext<ChatContextType | undefined>(undefined)

export const useChat = (): ChatContextType => {
  const context = useContext(ChatContext)
  if (!context) {
    throw new Error('useChat must be used within a ChatProvider')
  }
  return context
}

interface ChatProviderProps {
  children: ReactNode
}

export const ChatProvider: React.FC<ChatProviderProps> = ({ children }) => {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>(ConnectionStatus.CONNECTING)
  const [connectionError, setConnectionError] = useState<string | null>(null)
  const { queueAndPlayAudio, resetAudioState } = useAudio()
  const [sessionLoadAttempted, setSessionLoadAttempted] = useState(false);
  // 添加工具状态
  const [toolState, setToolState] = useState<{
    type: 'NAGISA_IS_USING_TOOL' | 'NAGISA_TOOL_USE_CONCLUDED';
    tool_name?: string;
    parameters?: Record<string, any>;
    action_text?: string;
  } | null>(null);
  // 添加工具开关状态
  const [toolsEnabled, setToolsEnabled] = useState<boolean>(false);
  const [ttsEnabled, setTtsEnabled] = useState<boolean>(true)

  // 处理位置请求的函数
  const handleLocationRequest = useCallback(async (data: any) => {
    console.log('收到位置请求:', data);
    
    try {
      // 获取地理位置服务实例
      const geolocationService = GeolocationService.getInstance();
      
      // 确保服务已初始化
      if (!geolocationService.isServiceInitialized()) {
        await geolocationService.initialize();
      }
      
      // 获取位置信息
      const locationData = await geolocationService.requestLocation();
      
      if (locationData) {
        // 添加session_id到位置数据中
        const locationDataWithSession = {
          ...locationData,
          session_id: currentSessionId
        };
        
        // 发送位置信息到后端
        const response = await fetch('/api/location/update', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(locationDataWithSession),
        });
        
        if (response.ok) {
          console.log('位置信息已成功发送到后端，session_id:', currentSessionId);
        } else {
          console.warn('位置信息发送失败');
        }
      } else {
        console.warn('无法获取位置信息');
      }
    } catch (error) {
      console.error('处理位置请求时出错:', error);
    }
  }, [currentSessionId]);

  // --- WebSocket connection for server push (e.g., REQUEST_LOCATION) ---
  const wsRef = useRef<WebSocket | null>(null);

  // Establish /ws/{session_id} connection whenever currentSessionId changes
  useEffect(() => {
    // Close previous ws if any
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch (_) {}
      wsRef.current = null;
    }

    if (!currentSessionId) return;

    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${protocol}://${window.location.host}/ws/${currentSessionId}`);
    wsRef.current = ws;

    ws.onopen = () => console.log("[WebSocket] connected for session", currentSessionId);
    ws.onclose = () => console.log("[WebSocket] closed for session", currentSessionId);
    ws.onerror = (e) => console.error("[WebSocket] error", e);
    
    // Handle incoming WebSocket messages
    ws.onmessage = async (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log("[WebSocket] received message:", data);
        
        // Handle location requests
        if (data.type === 'REQUEST_LOCATION') {
          console.log('WebSocket received location request');
          await handleLocationRequest(data);
        }
      } catch (error) {
        console.error("[WebSocket] failed to parse message:", error);
      }
    };

    return () => {
      try {
        ws.close();
      } catch (_) {}
    };
  }, [currentSessionId, handleLocationRequest]);

  // 添加更新工具状态的函数
  const updateToolsEnabled = useCallback(async (enabled: boolean) => {
    try {
      const response = await fetch('/api/chat/tools-enabled', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ enabled }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      if (data.success) {
        setToolsEnabled(data.tools_enabled);
      }
    } catch (error) {
      console.error('更新工具状态失败:', error);
      throw error;
    }
  }, []);

  // 更新 TTS 状态
  const updateTtsEnabled = useCallback(async (enabled: boolean) => {
    try {
      const response = await fetch('/api/chat/tts-enabled', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ enabled }),
      });

      if (!response.ok) {
        throw new Error('Failed to update TTS status');
      }

      const data = await response.json();
      setTtsEnabled(data.tts_enabled);
    } catch (error) {
      console.error('Error updating TTS status:', error);
      throw error;
    }
  }, []);

  // 检查与后端的连接
  const checkConnection = useCallback(async (): Promise<boolean> => {
    try {
      setConnectionStatus(ConnectionStatus.CONNECTING)
      setConnectionError(null)
      
      const response = await fetch('/api/history/sessions', { 
        signal: AbortSignal.timeout(5000) // 5秒超时
      })
      
      if (response.ok) {
        setConnectionStatus(ConnectionStatus.CONNECTED)
        return true
      } else {
        setConnectionStatus(ConnectionStatus.ERROR)
        setConnectionError(`服务器返回错误: ${response.status}`)
        return false
      }
    } catch (error) {
      console.error('连接检查失败:', error)
      setConnectionStatus(ConnectionStatus.DISCONNECTED)
      setConnectionError(error instanceof Error ? error.message : '无法连接到服务器')
      return false
    }
  }, [])

  // 刷新会话列表
  const refreshSessions = useCallback(async (): Promise<ChatSession[]> => {
    try {
      const response = await fetch('/api/history/sessions')
      if (!response.ok) {
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(`获取会话列表失败: ${response.status}`);
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data = await response.json()
      setSessions(data)
      setConnectionStatus(ConnectionStatus.CONNECTED); // Successfully fetched
      return data;
    } catch (error) {
      console.error('获取会话列表失败:', error);
      if (!(error instanceof DOMException && error.name === 'AbortError')) { // Don't set error if it's an abort
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(error instanceof Error ? error.message : '获取会话列表失败');
      }
      throw error;
    }
  }, [])

  // 创建新会话
  const createNewSession = useCallback(async (name?: string): Promise<string> => {
    console.log('createNewSession called with name:', name);
    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      console.log('Checking connection...');
      const canConnect = await checkConnection();
      if (!canConnect) {
        console.error('Connection check failed:', connectionError);
        throw new Error(connectionError || "无法连接到服务器，请重试。");
      }
    }
    try {
      console.log('Sending create session request...');
      const response = await fetch('/api/history/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name }),
      });
      
      if (!response.ok) {
        console.error('Create session request failed:', response.status);
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(`创建新会话失败: ${response.status}`);
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data = await response.json();
      console.log('Create session response:', data);
      const newSessionId = data.session_id;
      
      localStorage.setItem('session_id', newSessionId);
      setCurrentSessionId(newSessionId);
      setMessages([]);

      // 同步 TTS 状态到后端
      try {
        await fetch('/api/chat/tts-enabled', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ enabled: ttsEnabled }),
        });
      } catch (error) {
        console.error('同步 TTS 状态失败:', error);
      }

      await refreshSessions();
      setConnectionStatus(ConnectionStatus.CONNECTED);
      return newSessionId;
    } catch (error) {
      console.error('Error in createNewSession:', error);
      setConnectionStatus(ConnectionStatus.ERROR);
      setConnectionError(error instanceof Error ? error.message : '创建新会话失败');
      throw error;
    }
  }, [refreshSessions, connectionStatus, checkConnection, connectionError, ttsEnabled]);

  // 切换会话
  const switchSession = useCallback(async (sessionId: string): Promise<void> => {
    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection();
      if (!canConnect) {
        throw new Error(connectionError || "无法连接到服务器，请重试。");
      }
    }
    try {
      const response = await fetch('/api/history/switch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ session_id: sessionId }),
      })
      
      if (!response.ok) {
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(`切换会话失败: ${response.status}`);
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      localStorage.setItem('session_id', sessionId)
      setCurrentSessionId(sessionId)

      // 同步 TTS 状态到后端
      try {
        await fetch('/api/chat/tts-enabled', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ enabled: ttsEnabled }),
        });
      } catch (error) {
        console.error('同步 TTS 状态失败:', error);
      }
      
      const historyResponse = await fetch(`/api/history/${sessionId}`)
      if (!historyResponse.ok) {
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(`获取历史记录失败: ${historyResponse.status}`);
        throw new Error(`获取历史记录失败: ${historyResponse.status}`)
      }
      
      const historyData = await historyResponse.json()
      if (!historyData.history || !Array.isArray(historyData.history)) {
        console.error('Invalid history data format:', historyData);
        setMessages([]);
        return;
      }

      const convertedMessages: Message[] = historyData.history
        .filter((msg: any) => {
          // 只保留真正的用户发言、AI文本和图片消息
          if (msg.role === 'user' && !msg.tool_request) return true;
          if (msg.role === 'assistant' && (!Array.isArray(msg.tool_calls) || msg.tool_calls.length === 0)) return true;
          if (msg.role === 'image') return true;
          return false;
        })
        .map((msg: any) => {
          // sender 判断更精确
          let sender: 'user' | 'bot';
          if (msg.role === 'user' && !msg.tool_request) {
            sender = 'user';
          } else if (msg.role === 'assistant' && (!Array.isArray(msg.tool_calls) || msg.tool_calls.length === 0)) {
            sender = 'bot';
          } else if (msg.role === 'image') {
            sender = 'bot';  // 图片消息也作为bot的消息显示
          } else {
            console.warn('Unexpected message format:', msg);
            return null;
          }

          let text = '';
          let files: FileData[] = [];
          
          // 处理消息内容
          if (msg.role === 'image') {
            // 处理图片消息
            text = msg.content || '';
            files.push({
              name: 'generated_image',
              type: 'image/png',
              data: `/api/images/${msg.image_path}`  // 通过API路由访问图片
            });
          } else if (typeof msg.content === 'string') {
            text = msg.content;
          } else if (Array.isArray(msg.content)) {
            // 合并所有文本内容
            const textContents = msg.content
              .filter((item: any) => item.text)
              .map((item: any) => item.text);
            text = textContents.join('\n');
            
            // 处理所有文件
            msg.content.forEach((item: any) => {
              if (item.inline_data) {
                files.push({
                  name: `image_${files.length + 1}`,
                  type: item.inline_data.mime_type,
                  data: `data:${item.inline_data.mime_type};base64,${item.inline_data.data}`
                });
              }
            });
          } else {
            console.warn('Invalid message content format:', msg.content);
            text = '消息格式错误';
          }

          // 处理工具状态
          let toolState = undefined;
          if (msg.tool_state) {
            toolState = {
              isUsingTool: msg.tool_state.is_using_tool || false,
              toolName: msg.tool_state.tool_name,
              action: msg.tool_state.action
            };
          }

          return {
            id: msg.id || uuidv4(),
            sender,
            text,
            files: files.length > 0 ? files : undefined,
            timestamp: new Date(msg.timestamp || Date.now()).getTime(),
            status: sender === 'user' ? MessageStatus.READ : undefined,
            streaming: false,
            isLoading: false,
            isRead: true,
            toolState
          };
        })
        .filter((msg: Message | null): msg is Message => msg !== null);

      setMessages(convertedMessages);
      setConnectionStatus(ConnectionStatus.CONNECTED);
    } catch (error) {
      console.error('切换会话失败:', error);
      setConnectionStatus(ConnectionStatus.ERROR);
      setConnectionError(error instanceof Error ? error.message : '切换会话失败');
      throw error;
    }
  }, [connectionStatus, checkConnection, connectionError, ttsEnabled]);

  // 删除会话
  const deleteSession = useCallback(async (sessionId: string): Promise<void> => {
    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection();
      if (!canConnect) {
        throw new Error(connectionError || "无法连接到服务器，请重试。");
      }
    }
    try {
      const response = await fetch(`/api/history/${sessionId}`, {
        method: 'DELETE',
      })
      if (!response.ok) {
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(`删除会话失败: ${response.status}`);
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      // 用最新的 sessions 判断
      const latestSessions = await refreshSessions();

      if (sessionId === currentSessionId) {
        if (latestSessions.length > 0) {
          await switchSession(latestSessions[0].id);
        } else {
          await createNewSession();
        }
      }

      setConnectionStatus(ConnectionStatus.CONNECTED);
    } catch (error) {
      console.error('删除会话失败:', error);
      setConnectionStatus(ConnectionStatus.ERROR);
      setConnectionError(error instanceof Error ? error.message : '删除会话失败');
      throw error;
    }
  }, [currentSessionId, createNewSession, refreshSessions, switchSession, connectionStatus, checkConnection, connectionError]);

  // 删除消息
  const deleteMessage = useCallback(async (messageId: string): Promise<void> => {
    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection();
      if (!canConnect) {
        throw new Error(connectionError || "无法连接到服务器，请重试。");
      }
    }
    
    // 确保有当前会话ID
    if (!currentSessionId) {
      throw new Error("没有活动的会话");
    }
    
    try {
      // 先检查消息是否存在于当前消息列表中
      const messageExists = messages.some(msg => msg.id === messageId);
      if (!messageExists) {
        console.error(`消息 ${messageId} 不存在于当前会话中`);
        throw new Error("消息不存在于当前会话中");
      }
      
      // 首先在前端更新消息列表，删除指定消息
      setMessages(prev => prev.filter(msg => msg.id !== messageId));
      
      // 调用后端API删除消息
      const response = await fetch('/api/messages/delete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: currentSessionId,
          message_id: messageId
        }),
      });
      
      const responseData = await response.json();
      
      if (!response.ok) {
        console.error('删除消息失败:', responseData);
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(`删除消息失败: ${responseData.detail || response.status}`);
        
        // 如果后端删除失败但前端已移除，恢复被删除的消息
        if (response.status === 404) {
          // 恢复被删除的消息列表
          await switchSession(currentSessionId);
          throw new Error(`删除消息失败: ${responseData.detail}`);
        }
      }
      
      // 删除成功后刷新会话列表
      await refreshSessions();
      setConnectionStatus(ConnectionStatus.CONNECTED);
    } catch (error) {
      console.error('删除消息失败:', error);
      setConnectionStatus(ConnectionStatus.ERROR);
      setConnectionError(error instanceof Error ? error.message : '删除消息失败');
      throw error;
    }
  }, [currentSessionId, connectionStatus, checkConnection, connectionError, refreshSessions, messages, switchSession]);

  // 初始化 Effect: ComponentDidMount
  useEffect(() => {
    const initLoad = async () => {
      // Attempt to establish connection and load initial data
      const connected = await checkConnection();
      if (!connected) {
        setSessionLoadAttempted(true); // Mark that an initial load attempt failed due to connection
        return;
      }

      // Connection successful, now try to load session list and then the active session
      try {
        await refreshSessions(); // Load all session details first

        const storedSessionId = localStorage.getItem('session_id');
        if (storedSessionId) {
          try {
            await switchSession(storedSessionId); // This loads messages for the session
            setSessionLoadAttempted(false); // Successfully loaded a session
          } catch (switchError) {
            console.error('初始化时无法切换到已存储会话，尝试创建新会话:', switchError);
            if (connectionStatus === ConnectionStatus.CONNECTED) {
              try {
                await createNewSession(); // This loads messages for new session & refreshes list
                setSessionLoadAttempted(false); // Successfully created a new session
              } catch (createError) {
                console.error('初始化时创建新会话失败（切换会话后）:', createError);
                setSessionLoadAttempted(true); // Failed to establish a session
              }
            } else {
              setSessionLoadAttempted(true); // Connection lost during switchSession attempt
            }
          }
        } else {
          // No stored session, create a new one
          try {
            await createNewSession();
            setSessionLoadAttempted(false); // Successfully created a new session
          } catch (createError) {
            console.error('初始化时创建新会话失败（无存储ID）:', createError);
            setSessionLoadAttempted(true); // Failed to establish a session
          }
        }
      } catch (refreshError) {
        // Error from refreshSessions()
        console.error('初始化时加载会话列表失败:', refreshError);
        setSessionLoadAttempted(true); // Mark that the load was attempted and failed
      }
    };

    initLoad();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run only once on mount

  // 尝试在重新连接后加载会话
  useEffect(() => {
    const loadSessionOnReconnect = async () => {
      if (connectionStatus === ConnectionStatus.CONNECTED && sessionLoadAttempted && !currentSessionId) {
        console.log("检测到重新连接，尝试加载/刷新会话...");
        setSessionLoadAttempted(false); // We are attempting to load now

        try {
          await refreshSessions(); // Load all session details first

          const storedSessionId = localStorage.getItem('session_id');
          if (storedSessionId) {
            try {
              await switchSession(storedSessionId);
              // Successfully loaded session on reconnect
            } catch (switchError) {
              console.error('重新连接后无法切换到已存储会话，尝试创建新会话:', switchError);
              if (connectionStatus === ConnectionStatus.CONNECTED) {
                try {
                  await createNewSession();
                } catch (createError) {
                  console.error('重新连接后创建新会话也失败（切换会话后）:', createError);
                  setSessionLoadAttempted(true); // Mark failed attempt
                }
              } else {
                 setSessionLoadAttempted(true); // Connection lost during switch
              }
            }
          } else {
            // No stored session, create a new one
            try {
              await createNewSession();
            } catch (createError) {
              console.error('重新连接后创建新会话失败（无存储ID）:', createError);
              setSessionLoadAttempted(true); // Mark failed attempt
            }
          }
        } catch (refreshError) {
          // Error from refreshSessions() during reconnect
          console.error('重新连接后加载会话列表失败:', refreshError);
          setSessionLoadAttempted(true); // Mark failed attempt so it can retry if connection cycles
        }
      }
    };

    loadSessionOnReconnect();
  }, [connectionStatus, sessionLoadAttempted, currentSessionId, refreshSessions, switchSession, createNewSession]);


  // 处理音频数据 - 确保返回一个Promise，该Promise在音频播放完成后resolve
  const processAudioData = useCallback(async (audioData: string, count: number): Promise<boolean> => {
    if (typeof audioData !== 'string' || audioData.length === 0) {
      console.warn('收到空的音频数据或格式不正确')
      return false
    }
    
    try {
      console.log(`开始播放音频 #${count}，等待播放完成...`);
      // 等待音频播放完成后再返回
      const startTime = Date.now();
      await queueAndPlayAudio(audioData);
      const duration = (Date.now() - startTime) / 1000;
      console.log(`音频 #${count} 已完成播放，耗时: ${duration.toFixed(2)}秒`);
      return true;
    } catch (error) {
      console.error(`音频 #${count} 处理失败:`, error);
      return false;
    }
  }, [queueAndPlayAudio])

  // 创建聊天API请求
  const createChatRequest = useCallback(async (text: string, files: FileData[] = [], userMessageId: string): Promise<Response> => {
    // 构造请求数据
    const messageData = JSON.stringify({
      id: userMessageId,
      text,
      timestamp: Date.now(),
      files: files.map(file => ({
        name: file.name,
        type: file.type,
        data: file.data
      }))
    })
    
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messageData,
        session_id: currentSessionId || localStorage.getItem('session_id') || "default_session",
        tts_enabled: ttsEnabled,
      }),
    })
    
    if (!response.ok) {
      // 更新消息为错误状态
      setMessages(prev => 
        prev.map(msg => 
          msg.id === userMessageId
            ? { ...msg, status: MessageStatus.ERROR }
            : msg
        )
      )
      
      setConnectionStatus(ConnectionStatus.ERROR);
      setConnectionError(`发送消息失败: ${response.status}`);
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    
    return response
  }, [currentSessionId, setConnectionStatus, setConnectionError, ttsEnabled])

  // 处理聊天API响应
  const processStreamResponse = useCallback(async (
    response: Response, 
    userMessageId: string
  ) => {
    // 直接添加一个Bot Message，初始状态为加载中
    const botMessageId = uuidv4();
    const botMessage = {
      id: botMessageId,
      sender: 'bot' as const,
      text: '',
      timestamp: Date.now(),
      streaming: true,
      isLoading: true,
      toolState: undefined
    };
    setMessages(prev => [...prev, botMessage]);

    // 处理流式响应
    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('无法读取响应流');
    }

    const decoder = new TextDecoder()
    let buffer = ''
    let currentKeyword: string | null = null
    let audioCount = 0
    let firstResponseReceived = false
    let finalAiMessageId: string | null = null // 存储后端返回的最终AI消息ID
    
    // 标记是否正在播放音频，用于同步控制
    let isProcessingChunk = false
    // 音频队列 - 存储待处理的数据
    let chunkQueue: {text: string, audio?: string, next?: any}[] = []
    
    // 处理文本和音频内容
    const handleContentUpdate = (data: any) => {
      if (!data) return;
      
      console.log(`收到新的文本和音频chunk:`, data);
      
      // 将文本和音频作为一个完整的chunk添加到队列
      chunkQueue.push({
        text: data.text || '',
        audio: data.audio,
        next: data.next
      });
      
      // 如果当前没有处理中的chunk，开始处理队列
      if (!isProcessingChunk) {
        console.log('当前没有正在处理的chunk，开始处理新的chunk');
        isProcessingChunk = true;
        processNextChunk(chunkQueue.shift()).catch(err => {
          console.error('处理chunk队列时出错:', err);
          isProcessingChunk = false;
        });
      } else {
        console.log('当前有chunk正在处理，新chunk已加入队列，等待处理');
      }
    };

    // 处理一个chunk的文本和音频
    const processNextChunk = async (chunk: any) => {
      if (!chunk) {
        isProcessingChunk = false;
        return;
      }

      try {
        // 处理文本 - 只有当有文本内容时才更新
        if (chunk.text !== undefined && chunk.text !== null) {
          // 过滤掉任何undefined或null值，确保文本是字符串
          let newText = '';
          if (typeof chunk.text === 'string') {
            newText = chunk.text;
          } else if (Array.isArray(chunk.text)) {
            newText = chunk.text.filter((t: unknown) => typeof t === 'string').join('');
          }

          if (newText.length > 0) {
            // 创建一个 Promise 来等待文本渲染完成
            const renderPromise = new Promise<void>((resolve) => {
              setMessages(prev => {
                const newMessages = prev.map(msg => {
                  if (msg.id === (finalAiMessageId || botMessageId)) {
                    // 确保现有文本是字符串
                    const existingText = typeof msg.text === 'string' ? msg.text : '';
                    const updatedText = existingText + newText;
                    return {
                      ...msg,
                      text: updatedText,
                      newText, // 添加新文本用于流式渲染
                      streaming: true,
                      // 保持加载状态，直到收到足够的文本内容
                      isLoading: updatedText.length < 10,
                      onRenderComplete: resolve
                    };
                  }
                  return msg;
                });
                return newMessages;
              });
            });

            // 等待文本渲染完成
            await renderPromise;
            
            // 添加小延迟以实现流式效果
            await new Promise(resolve => setTimeout(resolve, 10));
          }
        }

        // 如果有音频且TTS已启用，使用音频队列系统播放
        if (ttsEnabled && chunk.audio && typeof chunk.audio === 'string' && chunk.audio.length > 0) {
          try {
            console.log('开始处理音频...');
            await processAudioData(chunk.audio, audioCount++);
            console.log('音频处理完成');
          } catch (error) {
            console.error('音频处理失败:', error);
          }
        }

        // 处理下一个chunk
        if (chunk.next) {
          await processNextChunk(chunk.next);
        } else {
          // 检查队列中是否还有其他chunk
          const nextChunk = chunkQueue.shift();
          if (nextChunk) {
            await processNextChunk(nextChunk);
          } else {
            // 所有chunk处理完成，更新消息状态
            setMessages(prev => 
              prev.map(msg => {
                if (msg.id === (finalAiMessageId || botMessageId)) {
                  // 确保最终文本是字符串
                  const finalText = typeof msg.text === 'string' ? msg.text : '';
                  return {
                    ...msg,
                    text: finalText,
                    streaming: false,
                    isLoading: false,
                    id: finalAiMessageId || botMessageId,
                    newText: undefined,
                    onRenderComplete: undefined
                  };
                }
                return msg;
              })
            );
            isProcessingChunk = false;
          }
        }
      } catch (error) {
        console.error('处理chunk时出错:', error);
        isProcessingChunk = false;
      }
    };
    
    // 处理标题更新事件
    const handleTitleUpdate = (data: any) => {
      // 确保payload存在并包含必要的字段
      if (data.payload && data.payload.session_id && data.payload.title) {
        const { session_id: updatedSessionId, title: newTitle } = data.payload;
        
        // 更新会话列表中的会话标题
        setSessions(prevSessions => 
          prevSessions.map(session => 
            session.id === updatedSessionId 
              ? { ...session, name: newTitle }
              : session
          )
        );
        
        // 如果更新的是当前活跃会话，立即刷新会话列表
        if (updatedSessionId === currentSessionId) {
          refreshSessions().catch(error => {
            console.error('刷新会话列表失败:', error);
          });
        }
      }
    };

    // 处理会话刷新事件
    const handleSessionRefresh = async (data: any) => {
      if (data.payload && data.payload.session_id) {
        const { session_id: refreshSessionId } = data.payload;
        
        // 如果刷新的是当前活跃会话，重新加载会话内容
        if (refreshSessionId === currentSessionId) {
          try {
            // 获取最新的会话历史
            const response = await fetch(`/api/history/${refreshSessionId}`);
            if (!response.ok) {
              throw new Error(`获取会话历史失败: ${response.status}`);
            }
            
            const historyData = await response.json();
            if (!historyData.history || !Array.isArray(historyData.history)) {
              throw new Error('无效的历史数据格式');
            }

            // 找到最后一条图片消息
            const lastImageMessage = historyData.history
              .filter((msg: any) => msg.role === 'image')
              .pop();

            if (lastImageMessage) {
              // 创建图片消息对象
              const imageMessage: Message = {
                id: lastImageMessage.id || uuidv4(),
                sender: 'bot',
                text: lastImageMessage.content || '',
                timestamp: new Date(lastImageMessage.timestamp || Date.now()).getTime(),
                files: [{
                  name: 'generated_image',
                  type: 'image/png',
                  data: `/api/images/${lastImageMessage.image_path}`
                }]
              };

              // 更新消息列表，添加图片消息
              setMessages(prev => [...prev, imageMessage]);
            }
          } catch (error) {
            console.error('刷新会话内容失败:', error);
            // 如果获取历史失败，回退到完整的会话切换
            await switchSession(refreshSessionId);
          }
        }
      }
    };

    // 处理消息状态更新
    const handleStatusUpdate = (data: any) => {
      if (data.status === 'sent') {
        // 后端确认消息已发送
        setMessages(prev => {
          return prev.map(msg => 
            msg.id === userMessageId
              ? { ...msg, status: MessageStatus.SENT }
              : msg
          );
        });
      } else if (data.status === 'read') {
        // 后端确认消息已读（已传递给LLM）
        setMessages(prev => {
          return prev.map(msg => 
            msg.id === userMessageId
              ? { ...msg, status: MessageStatus.READ }
              : msg
          );
        });
      } else if (data.status === 'error') {
        // 处理错误状态
        console.error('消息处理错误:', data.error);
        setMessages(prev => 
          prev.map(msg => 
            msg.id === userMessageId
              ? { ...msg, status: MessageStatus.ERROR }
              : msg
          )
        );
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(data.error || '发送消息失败');
      }
    };

    // 处理AI消息ID
    const handleAiMessageId = (data: any) => {
      if (data.message_id && !finalAiMessageId) {
        finalAiMessageId = data.message_id;
        // Immediately update the message ID to match the backend
        console.log(`Updating bot message ID from ${botMessageId} to ${finalAiMessageId}`);
        setMessages(prev => 
          prev.map(msg => {
            if (msg.id === botMessageId) {
              return { ...msg, id: finalAiMessageId! };
            }
            return msg;
          })
        );
      }
    };

    // 处理关键词和动作
    const handleKeyword = (data: any) => {
      if (data.keyword && data.keyword !== currentKeyword) {
        currentKeyword = data.keyword;
        
        // 根据关键词播放对应的Live2D动作
        if (currentKeyword) {
          playMotion(currentKeyword);
        }
      }
    };

    // 处理工具状态
    const handleToolState = (data: any) => {
      if (data.type === 'NAGISA_IS_USING_TOOL') {
        // 更新当前机器人消息的工具状态
        setMessages(prev => 
          prev.map(msg => {
            if (msg.id === botMessageId || (finalAiMessageId && msg.id === finalAiMessageId)) {
              return {
                ...msg,
                toolState: {
                  isUsingTool: true,
                  toolName: data.tool_name,
                  toolParams: data.parameters,
                  action: data.action_text
                }
              };
            }
            return msg;
          })
        );
        // 更新全局工具状态
        setToolState(data);
      } else if (data.type === 'NAGISA_TOOL_USE_CONCLUDED') {
        // 清除当前机器人消息的工具状态
        setMessages(prev => 
          prev.map(msg => {
            if (msg.id === botMessageId || (finalAiMessageId && msg.id === finalAiMessageId)) {
              return {
                ...msg,
                toolState: {
                  isUsingTool: false
                }
              };
            }
            return msg;
          })
        );
        // 清除全局工具状态
        setToolState(data);
      }
    };

    // 处理第一次响应
    const handleFirstResponse = (data: any) => {
      if (!firstResponseReceived && data.keyword) {
        firstResponseReceived = true;
      }
    };

    // 使用外部定义的位置请求处理函数

    // 处理一行数据
    const processLine = (line: string) => {
      if (line.trim() === '') return;
      
      if (line.startsWith('data: ')) {
        const jsonData = line.slice(6);
        
        try {
          const data = JSON.parse(jsonData);
          
          // 优先处理标题更新事件
          if (data.type === 'TITLE_UPDATE') {
            handleTitleUpdate(data);
            return;
          }
          
          // 处理会话刷新事件
          if (data.type === 'SESSION_REFRESH') {
            handleSessionRefresh(data);
            return;
          }
          
          // 处理位置请求事件
          if (data.type === 'REQUEST_LOCATION') {
            handleLocationRequest(data);
            return;
          }
          
          // 处理消息状态更新
          if (data.status) {
            handleStatusUpdate(data);
            return;
          }
          
          // 处理后端返回的AI消息ID
          handleAiMessageId(data);
          
          // 处理第一次响应
          handleFirstResponse(data);
          
          // 处理关键词
          handleKeyword(data);
          
          // 处理工具状态
          if (data.type === 'NAGISA_IS_USING_TOOL' || data.type === 'NAGISA_TOOL_USE_CONCLUDED') {
            handleToolState(data);
            return;
          }
          
          // 处理文本和音频
          handleContentUpdate(data);
        } catch (e) {
          console.error('解析响应数据时出错:', e);
        }
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        // Wait for all chunks to be processed
        while (chunkQueue.length > 0 || isProcessingChunk) {
          await new Promise(resolve => setTimeout(resolve, 100));
        }
        
        // After streaming all sentences, only update streaming flag
        setMessages(prev => 
          prev.map(msg => {
            if (msg.id === botMessageId || (finalAiMessageId && msg.id === finalAiMessageId)) {
              return { 
                ...msg, 
                streaming: false,
                id: finalAiMessageId || botMessageId
              };
            }
            return msg;
          })
        );
        
        // Refresh session list to update latest state
        refreshSessions();
        break;
      }
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';
      
      // 处理每一行数据
      for (const line of lines) {
        processLine(line);
      }
    }
  }, [processAudioData, refreshSessions, setConnectionError, setConnectionStatus, playMotion, setSessions, currentSessionId, ttsEnabled])

  // 主发送消息函数
  const sendMessage = useCallback(async (text: string, files: FileData[] = []) => {
    if (text.trim() === '' && files.length === 0) return
    
    // 检查连接状态
    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection();
      if (!canConnect) {
        setMessages(prev => {
          // 找到最后一条机器人消息，如果是加载状态的话，更新它为错误消息
          const botMessages = prev.filter(msg => msg.sender === 'bot' && msg.isLoading);
          if (botMessages.length > 0) {
            const lastBotMessage = botMessages[botMessages.length - 1];
            return prev.map(msg => 
              msg.id === lastBotMessage.id 
                ? { ...msg, text: "错误: 无法连接到服务器。请检查网络连接或稍后重试。", isLoading: false }
                : msg
            );
          }
          return prev;
        });
        return;
      }
    }
    
    // 重置音频状态
    await resetAudioState()
    
    // 创建用户消息
    const userMessage: Message = {
      id: uuidv4(),
      sender: 'user',
      text,
      files,
      timestamp: Date.now(),
      status: MessageStatus.SENDING
    }
    
    // 添加到消息列表
    setMessages(prev => [...prev, userMessage])
    
    try {
      // 创建并发送API请求
      const response = await createChatRequest(text, files, userMessage.id)
      
      // 处理流式响应
      await processStreamResponse(response, userMessage.id)
    } catch (error) {
      console.error('Error sending message:', error)
      // 更新用户消息为错误状态
      setMessages(prev => 
        prev.map(msg => 
          msg.id === userMessage.id
            ? { ...msg, status: MessageStatus.ERROR }
            : msg
        )
      )
      
      setConnectionStatus(ConnectionStatus.ERROR);
      const errorMsg = error instanceof Error ? error.message : '发送消息失败';
      setConnectionError(errorMsg);
    } finally {
      setIsLoading(false)
    }
  }, [connectionStatus, checkConnection, createChatRequest, processStreamResponse, resetAudioState, setConnectionStatus, setConnectionError])

  const clearChat = useCallback(() => {
    setMessages([])
  }, [])

  // 添加刷新标题方法
  const refreshTitle = useCallback(async (sessionId: string): Promise<void> => {
    try {
      if (!sessionId) {
        throw new Error('会话ID不能为空');
      }

      const response = await fetch('/api/history/generate-title', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ session_id: sessionId }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      // 如果成功生成了新标题，更新会话列表
      if (data.success && data.title) {
        // 更新本地状态中的会话标题
        setSessions(prevSessions => 
          prevSessions.map(session => 
            session.id === sessionId 
              ? { ...session, name: data.title }
              : session
          )
        );
      }
    } catch (error) {
      console.error('刷新标题失败:', error);
      throw error;
    }
  }, [setSessions]);

  // 一键生成图片
  const generateImage = useCallback(async (sessionId: string): Promise<{success: boolean, image_path?: string, error?: string}> => {
    try {
      const response = await fetch('/api/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
      });
      const data = await response.json();
      return data;
    } catch (error: any) {
      return { success: false, error: error.message || 'Network error' };
    }
  }, []);

  return (
    <ChatContext.Provider value={{
      messages,
      isLoading,
      sessions,
      currentSessionId,
      connectionStatus,
      connectionError,
      sendMessage,
      clearChat,
      createNewSession,
      switchSession,
      deleteSession,
      deleteMessage,
      refreshSessions,
      checkConnection,
      refreshTitle,
      toolState,
      toolsEnabled,
      updateToolsEnabled,
      generateImage,
      ttsEnabled,
      updateTtsEnabled
    }}>
      {children}
    </ChatContext.Provider>
  )
}
