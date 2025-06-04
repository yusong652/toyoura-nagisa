import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message, FileData, ChatContextType, ChatSession, ConnectionStatus, MessageStatus } from '../types/chat'
import { useAudio } from './AudioContext.tsx'
import { playMotion } from '../utils/live2d'

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
  const refreshSessions = useCallback(async (): Promise<void> => {
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
      await refreshSessions();
      setConnectionStatus(ConnectionStatus.CONNECTED);
      return newSessionId;
    } catch (error) {
      console.error('Error in createNewSession:', error);
      setConnectionStatus(ConnectionStatus.ERROR);
      setConnectionError(error instanceof Error ? error.message : '创建新会话失败');
      throw error;
    }
  }, [refreshSessions, connectionStatus, checkConnection, connectionError]);

  // 切换会话
  const switchSession = useCallback(async (sessionId: string): Promise<void> => {
     if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection();
      if (!canConnect) {
        // checkConnection sets connectionError state.
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
      
      const historyResponse = await fetch(`/api/history/${sessionId}`)
      if (!historyResponse.ok) {
        setConnectionStatus(ConnectionStatus.ERROR);
        setConnectionError(`获取历史记录失败: ${historyResponse.status}`);
        throw new Error(`获取历史记录失败: ${historyResponse.status}`)
      }
      
      const historyData = await historyResponse.json()
      const convertedMessages: Message[] = historyData.history
        .filter((msg: any) => {
          // 只保留真正的用户发言和AI文本
          if (msg.role === 'user' && !msg.tool_request) return true;
          if (msg.role === 'assistant' && (!Array.isArray(msg.tool_calls) || msg.tool_calls.length === 0)) return true;
          return false;
        })
        .map((msg: any) => {
          // sender 判断更精确
          let sender: 'user' | 'bot';
          if (msg.role === 'user' && !msg.tool_request) {
            sender = 'user';
          } else if (msg.role === 'assistant' && (!Array.isArray(msg.tool_calls) || msg.tool_calls.length === 0)) {
            sender = 'bot';
          } else {
            // 理论上不会走到这里
            sender = 'bot';
          }
          let text = ''
          let files: FileData[] = []
          // 处理消息内容
          if (typeof msg.content === 'string') {
            text = msg.content
          } else if (Array.isArray(msg.content)) {
            // 合并所有文本内容
            const textContents = msg.content
              .filter((item: any) => item.text)
              .map((item: any) => item.text)
            text = textContents.join('\n')
            // 处理所有文件
            msg.content.forEach((item: any) => {
              if (item.inline_data) {
                files.push({
                  name: `image_${files.length + 1}`,
                  type: item.inline_data.mime_type,
                  data: `data:${item.inline_data.mime_type};base64,${item.inline_data.data}`
                })
              }
            })
          }
          // 处理工具状态
          let toolState = undefined
          if (msg.tool_state) {
            toolState = {
              isUsingTool: msg.tool_state.is_using_tool || false,
              toolName: msg.tool_state.tool_name,
              action: msg.tool_state.action
            }
          }
          return {
            id: msg.id || uuidv4(),
            sender,
            text,
            files: files.length > 0 ? files : undefined,
            timestamp: new Date(msg.timestamp).getTime(),
            status: sender === 'user' ? MessageStatus.READ : undefined,
            streaming: false,
            isLoading: false,
            isRead: true,
            toolState
          }
        })
      setMessages(convertedMessages)
      setConnectionStatus(ConnectionStatus.CONNECTED);
    } catch (error) {
      console.error('切换会话失败:', error);
      setConnectionStatus(ConnectionStatus.ERROR);
      setConnectionError(error instanceof Error ? error.message : '切换会话失败');
      throw error;
    }
  }, [connectionStatus, checkConnection, connectionError])

  // 删除会话
  const deleteSession = useCallback(async (sessionId: string): Promise<void> => {
    if (connectionStatus !== ConnectionStatus.CONNECTED && connectionStatus !== ConnectionStatus.CONNECTING) {
      const canConnect = await checkConnection();
      if (!canConnect) {
        // checkConnection sets connectionError state.
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
      
      if (sessionId === currentSessionId) {
        await createNewSession()
      }
      await refreshSessions()
      setConnectionStatus(ConnectionStatus.CONNECTED);
    } catch (error) {
      console.error('删除会话失败:', error);
      setConnectionStatus(ConnectionStatus.ERROR);
      setConnectionError(error instanceof Error ? error.message : '删除会话失败');
      throw error;
    }
  }, [currentSessionId, createNewSession, refreshSessions, connectionStatus, checkConnection, connectionError])

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

  // 添加用户消息到聊天记录
  const addUserMessage = useCallback((text: string, files: FileData[] = []): string => {
    // 创建用户消息
    const userMessage: Message = {
      id: uuidv4(), // 使用前端生成的UUID
      sender: 'user',
      text,
      files,
      timestamp: Date.now(),
      status: MessageStatus.SENDING // 初始状态为发送中
    }
    
    // 添加到消息列表
    setMessages(prev => [...prev, userMessage])
    
    return userMessage.id
  }, [])

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
  }, [currentSessionId, setConnectionStatus, setConnectionError])

  // 处理聊天API响应
  const processStreamResponse = useCallback(async (
    response: Response, 
    userMessageId: string
  ) => {
    // 处理流式响应
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let currentText = ''
    let currentKeyword: string | null = null
    let audioCount = 0
    let firstResponseReceived = false
    let botMessageId = uuidv4() // 直接生成机器人消息ID
    let finalAiMessageId: string | null = null // 存储后端返回的最终AI消息ID
    
    // 标记是否正在播放音频，用于同步控制
    let isProcessingChunk = false
    // 音频队列 - 存储待处理的数据
    let chunkQueue: {text: string, audio?: string}[] = []
    
    // 添加一个函数来处理下一个文字+音频chunk，确保顺序播放
    const processNextChunk = async () => {
      if (chunkQueue.length === 0 || isProcessingChunk) return;
      
      isProcessingChunk = true;
      const nextItem = chunkQueue.shift()!;
      
      try {
        // 1. 先更新文本
        if (nextItem.text) {
          currentText += nextItem.text;
          setMessages(prev => 
            prev.map(msg => {
              if (msg.id === botMessageId || (finalAiMessageId && msg.id === finalAiMessageId)) {
                // Create a new message object to ensure state updates trigger scroll
                return { 
                  ...msg, 
                  text: currentText, 
                  streaming: true,
                  isLoading: false,
                  // Add a small timestamp increment to force UI update
                  timestamp: Date.now()
                };
              }
              return msg;
            })
          );
        }
        
        // 2. 如果有音频，播放并等待完成
        if (nextItem.audio) {
          audioCount++;
          console.log(`处理音频 #${audioCount}, 等待播放完成...`);
          
          // 确保等待音频真正播放完成
          const audioResult = await processAudioData(nextItem.audio, audioCount);
          console.log(`音频 #${audioCount} 播放完成, 结果: ${audioResult}`);
        } else {
          // 如果只有文本没有音频，添加一个短暂停顿
          await new Promise(resolve => setTimeout(resolve, 10));
        }
      } catch (error) {
        console.error('处理chunk时出错:', error);
      } finally {
        isProcessingChunk = false;
        // 继续处理下一个
        processNextChunk();
      }
    };
    
    // 直接添加一个机器人消息，初始状态为加载中
    setMessages(prev => [...prev, {
      id: botMessageId,
      sender: 'bot',
      text: '',
      timestamp: Date.now(),
      isLoading: true // 初始显示为加载状态
    }])
    
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

    // 处理文本和音频内容
    const handleContentUpdate = (data: any) => {
      if (data.text) {
        console.log(`收到新的文本和音频chunk: ${data.text.length}字符${data.audio ? '，有音频' : '，无音频'}`);
        
        // 将文本和音频作为一个完整的chunk添加到队列
        chunkQueue.push({
          text: data.text,
          audio: data.audio
        });
        
        // 如果当前没有处理中的chunk，开始处理队列
        if (!isProcessingChunk) {
          console.log('当前没有正在处理的chunk，开始处理新的chunk');
          processNextChunk().catch(err => {
            console.error('处理chunk队列时出错:', err);
          });
        } else {
          console.log('当前有chunk正在处理，新chunk已加入队列，等待处理');
        }
      }
    };

    // 处理第一次响应
    const handleFirstResponse = (data: any) => {
      if (!firstResponseReceived && data.keyword) {
        firstResponseReceived = true;
      }
    };

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
        
        // After streaming all sentences, only update isLoading and streaming flags
        setMessages(prev => 
          prev.map(msg => {
            if (msg.id === botMessageId || (finalAiMessageId && msg.id === finalAiMessageId)) {
              return { 
                ...msg, 
                isLoading: false,
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
  }, [processAudioData, refreshSessions, setConnectionError, setConnectionStatus, playMotion, setSessions, currentSessionId])

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
                ? { ...msg, text: `错误: 无法连接到服务器。请检查网络连接或稍后重试。`, isLoading: false } 
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
    
    // 添加用户消息，初始状态为正在发送
    const userMessageId = addUserMessage(text, files)
    
    try {
      // 创建并发送API请求
      const response = await createChatRequest(text, files, userMessageId)
      
      // 处理流式响应
      await processStreamResponse(response, userMessageId)
    } catch (error) {
      console.error('Error sending message:', error)
      // 更新用户消息为错误状态
      setMessages(prev => 
        prev.map(msg => 
          msg.id === userMessageId
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
  }, [
    addUserMessage, 
    resetAudioState, 
    createChatRequest, 
    processStreamResponse, 
    connectionStatus, 
    checkConnection, 
    setConnectionStatus, 
    setConnectionError
  ])

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
      toolsEnabled,  // 添加工具开关状态
      updateToolsEnabled  // 添加更新工具状态的函数
    }}>
      {children}
    </ChatContext.Provider>
  )
} 