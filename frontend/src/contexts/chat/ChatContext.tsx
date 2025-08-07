import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message, FileData, ChatContextType, MessageStatus } from '../../types/chat'
import { useAudio } from '../audio/AudioContext'
import { useTools } from '../tools/ToolsContext'
import { useSession } from '../session/SessionContext'
import { playMotion } from '../../utils/live2d'
import { chatService, sessionService } from '../../services/api'
import { useChatMessage } from './useChatMessage'

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
  const [isLoading, setIsLoading] = useState(false)
  const { queueAndPlayAudio, resetAudioState } = useAudio()
  const {
    toolState,
    toolsEnabled,
    ttsEnabled,
    updateToolsEnabled,
    updateTtsEnabled,
    setToolState
  } = useTools()
  
  // 从SessionContext获取会话相关状态和方法
  const {
    currentSessionId,
    refreshSessions: sessionRefreshSessions,
    switchSession: sessionSwitchSession
  } = useSession()
  
  // 使用重构的消息管理钩子
  const {
    messages,
    setMessages,
    deleteMessage,
    clearChat
  } = useChatMessage({
    currentSessionId,
    sessionRefreshSessions,
    sessionSwitchSession
  })


  // 注意：会话相关的功能已经移至 SessionContext，组件应直接使用 useSession()
  // 消息管理功能已经移至 useChatMessage 钩子

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
    try {
      const sessionId = currentSessionId || localStorage.getItem('session_id') || "default_session";
      return await chatService.sendMessage(text, files, sessionId, userMessageId, ttsEnabled);
    } catch (error) {
      // 更新消息为错误状态
      setMessages(prev => 
        prev.map(msg => 
          msg.id === userMessageId
            ? { ...msg, status: MessageStatus.ERROR }
            : msg
        )
      )
      throw error;
    }
  }, [currentSessionId, ttsEnabled])

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
    let buffer = '' // 每次新请求都重新初始化buffer
    let currentKeyword: string | null = null
    let audioCount = 0
    let firstResponseReceived = false
    let finalAiMessageId: string | null = null // 存储后端返回的最终AI消息ID
    
    // 标记是否正在播放音频，用于同步控制 - 每次新请求都重置
    let isProcessingChunk = false
    // 音频队列 - 存储待处理的数据 - 每次新请求都清空
    let chunkQueue: {text: string, audio?: string, index?: number, next?: any}[] = []
    // 排序缓存 - 确保chunk按正确顺序处理
    let chunkBuffer: Map<number, {text: string, audio?: string, next?: any}> = new Map()
    let expectedChunkIndex = 0
    
    // 处理文本和音频内容
    const handleContentUpdate = (data: any) => {
      if (!data) return;
      
      console.log(`收到新的文本和音频chunk:`, data);
      
      // 检查是否有index字段用于排序
      if (data.index !== undefined && typeof data.index === 'number') {
        // 使用排序缓存处理有序的chunk
        handleOrderedChunk(data);
      } else {
        // 对于没有index的chunk，直接处理（保持兼容性）
        handleUnorderedChunk(data);
      }
    };

    // 处理有序chunk（带index字段）
    const handleOrderedChunk = (data: any) => {
      const chunkIndex = data.index;
      
      // 将chunk添加到缓存
      chunkBuffer.set(chunkIndex, {
        text: data.text || '',
        audio: data.audio,
        next: data.next
      });
      
      console.log(`缓存chunk #${chunkIndex}，期望index: ${expectedChunkIndex}`);
      
      // 处理所有连续的chunk
      while (chunkBuffer.has(expectedChunkIndex)) {
        const chunk = chunkBuffer.get(expectedChunkIndex)!;
        chunkBuffer.delete(expectedChunkIndex);
        
        console.log(`处理有序chunk #${expectedChunkIndex}`);
        
        // 添加到处理队列
        chunkQueue.push({
          text: chunk.text,
          audio: chunk.audio,
          index: expectedChunkIndex,
          next: chunk.next
        });
        
        expectedChunkIndex++;
        
        // 如果当前没有处理中的chunk，开始处理队列
        if (!isProcessingChunk) {
          console.log('开始处理有序chunk队列');
          isProcessingChunk = true;
          processNextChunk(chunkQueue.shift()).catch(err => {
            console.error('处理有序chunk队列时出错:', err);
            isProcessingChunk = false;
          });
        }
      }
    };

    // 处理无序chunk（兼容旧格式）
    const handleUnorderedChunk = (data: any) => {
      // 将文本和音频作为一个完整的chunk添加到队列
      chunkQueue.push({
        text: data.text || '',
        audio: data.audio,
        next: data.next
      });
      
      // 如果当前没有处理中的chunk，开始处理队列
      if (!isProcessingChunk) {
        console.log('开始处理无序chunk队列');
        isProcessingChunk = true;
        processNextChunk(chunkQueue.shift()).catch(err => {
          console.error('处理无序chunk队列时出错:', err);
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
        // 刷新会话列表以获取最新状态
        sessionRefreshSessions().catch(error => {
          console.error('刷新会话列表失败:', error);
        });
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
            await sessionSwitchSession(refreshSessionId);
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
          
          // 位置请求事件在普通WebSocket连接中处理，这里不需要重复处理
          
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
        
        // 显式清理状态，确保不会影响下一次请求
        chunkQueue = [];
        chunkBuffer.clear();
        expectedChunkIndex = 0;
        isProcessingChunk = false;
        buffer = '';
        console.log('[DEBUG] Stream processing completed, all state cleared including ordering buffer');
        
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
        sessionRefreshSessions();
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
  }, [processAudioData, sessionRefreshSessions, playMotion, currentSessionId, ttsEnabled, sessionSwitchSession])

  // 主发送消息函数
  const sendMessage = useCallback(async (text: string, files: FileData[] = []) => {
    if (text.trim() === '' && files.length === 0) return
    
    // 重置音频状态 - 确保清理上一次请求的残留状态
    await resetAudioState()
    console.log('[DEBUG] Starting new message request, audio state reset');
    
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
      
    } finally {
      setIsLoading(false)
    }
  }, [createChatRequest, processStreamResponse, resetAudioState])



  // 一键生成图片
  const generateImage = useCallback(async (sessionId: string): Promise<{success: boolean, image_path?: string, error?: string}> => {
    const result = await chatService.generateImage(sessionId);
    
    // 如果图片生成成功，重新获取会话历史以获取最新的图片消息
    if (result.success && sessionId === currentSessionId) {
      try {
        // 获取最新的会话历史
        const historyData = await sessionService.getSessionHistory(sessionId);
        if (historyData.history && Array.isArray(historyData.history)) {
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

            // 添加图片消息到当前消息列表
            setMessages(prev => [...prev, imageMessage]);
          }
        }
      } catch (error) {
        console.error('获取生成的图片消息失败:', error);
      }
    }
    
    return result;
  }, [currentSessionId]);

  return (
    <ChatContext.Provider value={{
      messages,
      isLoading,
      sendMessage,
      clearChat,
      deleteMessage,
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
