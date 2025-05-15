import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect, useRef } from 'react'
import { startLipSync, stopLipSync } from '../utils/live2d'

interface AudioContextType {
  queueAndPlayAudio: (audioBase64: string) => void
  resetAudioState: () => Promise<void>
}

const AudioContext = createContext<AudioContextType | undefined>(undefined)

export const useAudio = (): AudioContextType => {
  const context = useContext(AudioContext)
  if (!context) {
    throw new Error('useAudio must be used within an AudioProvider')
  }
  return context
}

interface AudioProviderProps {
  children: ReactNode
}

export const AudioProvider: React.FC<AudioProviderProps> = ({ children }) => {
  // 使用useRef而不是useState来存储audioContext，避免重渲染问题
  const audioContextRef = useRef<AudioContext | null>(null)
  const [currentSource, setCurrentSource] = useState<AudioBufferSourceNode | null>(null)
  const [currentAnalyser, setCurrentAnalyser] = useState<AnalyserNode | null>(null)
  const [audioQueue, setAudioQueue] = useState<string[]>([])
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentAudioPromise, setCurrentAudioPromise] = useState<Promise<void> | null>(null)
  const [audioContextInitialized, setAudioContextInitialized] = useState(false)
  // 添加一个ref来跟踪队列状态，避免闭包问题
  const audioQueueRef = useRef<string[]>([])
  const isPlayingRef = useRef<boolean>(false)
  // 添加一个ref来跟踪是否应该停止当前音频
  const shouldStopCurrentAudioRef = useRef<boolean>(false)

  // 当audioQueue状态更新时，同步更新ref
  useEffect(() => {
    audioQueueRef.current = audioQueue;
  }, [audioQueue]);

  // 当isPlaying状态更新时，同步更新ref
  useEffect(() => {
    isPlayingRef.current = isPlaying;
  }, [isPlaying]);

  // 初始化AudioContext并确保它被激活
  useEffect(() => {
    // 创建静音音频以激活AudioContext
    const initializeAudioContext = async () => {
      if (!audioContextRef.current) {
        try {
          console.log('创建AudioContext...')
          audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)()
          
          // 检查AudioContext状态
          if (audioContextRef.current.state === 'suspended') {
            console.log('AudioContext处于suspended状态，尝试恢复...')
            
            // 创建一个短暂的静音音频来激活AudioContext
            const silentBuffer = audioContextRef.current.createBuffer(1, 1, 22050)
            const source = audioContextRef.current.createBufferSource()
            source.buffer = silentBuffer
            source.connect(audioContextRef.current.destination)
            source.start()
            
            // 尝试恢复AudioContext
            try {
              await audioContextRef.current.resume()
              console.log('AudioContext已恢复:', audioContextRef.current?.state)
              setAudioContextInitialized(true)
            } catch (err) {
              console.error('恢复AudioContext失败:', err)
            }
          } else {
            console.log('AudioContext状态:', audioContextRef.current.state)
            setAudioContextInitialized(true)
          }
        } catch (error) {
          console.error('初始化AudioContext失败:', error)
        }
      }
    }

    // 添加用户交互事件监听器来激活AudioContext
    const activateAudioContext = async () => {
      if (audioContextRef.current && audioContextRef.current.state === 'suspended') {
        try {
          await audioContextRef.current.resume()
          console.log('用户交互后AudioContext已恢复:', audioContextRef.current.state)
          setAudioContextInitialized(true)
        } catch (err) {
          console.error('用户交互后恢复AudioContext失败:', err)
        }
      }
    }

    // 初始化
    initializeAudioContext()

    // 添加事件监听器
    const events = ['click', 'touchstart', 'keydown']
    events.forEach(event => document.addEventListener(event, activateAudioContext, { once: true }))

    return () => {
      // 清理事件监听器
      events.forEach(event => document.removeEventListener(event, activateAudioContext))
    }
  }, [])

  // 获取AudioContext并确保它已激活
  const getAudioContext = useCallback(async () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)()
    }
    
    // 如果状态是suspended，尝试恢复
    if (audioContextRef.current.state === 'suspended') {
      try {
        console.log('尝试恢复AudioContext...')
        await audioContextRef.current.resume()
        console.log('AudioContext恢复成功，当前状态:', audioContextRef.current.state)
      } catch (err: any) {
        console.warn('恢复AudioContext失败:', err)
      }
    }
    
    return audioContextRef.current
  }, [])

  // 停止当前播放的音频
  const stopCurrentAudio = useCallback(async () => {
    // 标记应该停止当前音频
    shouldStopCurrentAudioRef.current = true;
    
    if (currentSource) {
      try {
        console.log('停止当前音频播放')
        currentSource.stop()
        currentSource.disconnect()
        if (currentAnalyser) {
          currentAnalyser.disconnect()
        }
        // 停止Live2D嘴型同步
        stopLipSync()
      } catch (e) {
        console.log('Audio already stopped')
      } finally {
        setCurrentSource(null)
        setCurrentAnalyser(null)
      }
    }
    
    // 重置标记
    shouldStopCurrentAudioRef.current = false;
  }, [currentSource, currentAnalyser])

  // 重置音频状态
  const resetAudioState = useCallback(async () => {
    console.log('重置音频状态')
    setAudioQueue([])
    audioQueueRef.current = [];
    await stopCurrentAudio()
    setIsPlaying(false)
    isPlayingRef.current = false;
    setCurrentAudioPromise(null)
    console.log('音频状态已重置')
  }, [stopCurrentAudio])

  // 播放单个音频
  const playAudioWithLipSync = useCallback((audioBase64: string): Promise<void> => {
    return new Promise(async (resolve, reject) => {
      try {
        // 重置停止标记
        shouldStopCurrentAudioRef.current = false;
        
        console.log('开始解码音频数据...')
        const audioBuffer = Uint8Array.from(atob(audioBase64), c => c.charCodeAt(0)).buffer
        const context = await getAudioContext()
        
        // 确保AudioContext处于running状态
        if (context.state === 'suspended') {
          console.log('AudioContext处于suspended状态，尝试恢复...')
          try {
            await context.resume()
            console.log('AudioContext已恢复')
          } catch (error) {
            console.warn('恢复AudioContext失败:', error)
          }
        }
        
        // 如果在解码前被标记为停止，则直接返回
        if (shouldStopCurrentAudioRef.current) {
          console.log('音频播放被取消（解码前）')
          resolve();
          return;
        }
        
        context.decodeAudioData(audioBuffer, (decodedData) => {
          try {
            // 如果在解码后被标记为停止，则直接返回
            if (shouldStopCurrentAudioRef.current) {
              console.log('音频播放被取消（解码后）')
              resolve();
              return;
            }

            const source = context.createBufferSource()
            source.buffer = decodedData
            
            const analyser = context.createAnalyser()
            analyser.fftSize = 256
            
            source.connect(analyser)
            analyser.connect(context.destination)

            setCurrentSource(source)
            setCurrentAnalyser(analyser)
            
            // 调用Live2D嘴型同步
            startLipSync(analyser)
            
            // 创建一个标志，表示音频是否已完成
            let audioCompleted = false;
            
            source.onended = () => {
              // 只有在音频正常播放完成时才处理
              if (!audioCompleted && !shouldStopCurrentAudioRef.current) {
                audioCompleted = true;
                stopLipSync()
                source.disconnect()
                analyser.disconnect()
                setCurrentSource(null)
                setCurrentAnalyser(null)
                resolve()
              }
            }

            // AudioBufferSourceNode没有onerror事件，使用try-catch处理错误
            try {
              console.log('开始播放音频，持续时间:', decodedData.duration, '秒')
              source.start(0)
              
              // 设置一个安全超时，确保即使onended不触发也能继续
              const safetyTimeout = setTimeout(() => {
                if (!audioCompleted && !shouldStopCurrentAudioRef.current) {
                  console.log('音频播放安全超时触发')
                  audioCompleted = true;
                  stopLipSync()
                  try {
                    source.stop()
                    source.disconnect()
                    analyser.disconnect()
                  } catch (e) {
                    // 忽略可能的错误
                  }
                  setCurrentSource(null)
                  setCurrentAnalyser(null)
                  resolve()
                }
              }, (decodedData.duration * 1000) + 500); // 音频长度 + 500ms 的安全边界
              
              // 如果音频被手动停止
              const checkStopInterval = setInterval(() => {
                if (shouldStopCurrentAudioRef.current && !audioCompleted) {
                  console.log('检测到手动停止音频请求')
                  audioCompleted = true;
                  clearTimeout(safetyTimeout);
                  clearInterval(checkStopInterval);
                  stopLipSync();
                  try {
                    source.stop();
                    source.disconnect();
                    analyser.disconnect();
                  } catch (e) {
                    // 忽略可能的错误
                  }
                  setCurrentSource(null);
                  setCurrentAnalyser(null);
                  resolve();
                }
              }, 100);
              
            } catch (error) {
              console.error('播放音频失败:', error)
              stopLipSync()
              source.disconnect()
              analyser.disconnect()
              setCurrentSource(null)
              setCurrentAnalyser(null)
              reject(error)
            }
          } catch (error) {
            console.error('设置音频源失败:', error)
            stopLipSync()
            reject(error)
          }
        }, (err: Error) => {
          console.error('音频解码失败:', err)
          stopLipSync()
          reject(new Error('音频解码失败: ' + err))
        })
      } catch (error) {
        console.error('处理音频数据失败:', error)
        stopLipSync()
        reject(error)
      }
    })
  }, [getAudioContext])

  // 播放队列中的下一个音频
  const playNextAudio = useCallback(async () => {
    console.log('尝试播放下一个音频，当前队列长度:', audioQueueRef.current.length, '是否正在播放:', isPlayingRef.current)
    
    if (isPlayingRef.current || audioQueueRef.current.length === 0) {
      console.log('跳过播放：正在播放或队列为空')
      return
    }
    
    setIsPlaying(true)
    isPlayingRef.current = true;
    
    const audioData = audioQueueRef.current[0]
    console.log('从队列中取出第一个音频数据，剩余:', audioQueueRef.current.length - 1)
    
    // 更新队列状态
    setAudioQueue(prev => {
      const newQueue = prev.slice(1)
      return newQueue
    })
    
    try {
      // 确保AudioContext已初始化并激活
      await getAudioContext()
      
      // 创建新的音频播放 Promise
      console.log('开始播放音频')
      const newAudioPromise = playAudioWithLipSync(audioData)
      setCurrentAudioPromise(newAudioPromise)
      await newAudioPromise
    } catch (error) {
      console.error('播放音频出错:', error)
    } finally {
      setIsPlaying(false)
      isPlayingRef.current = false;
      setCurrentAudioPromise(null)
      
      // 使用最新的队列状态检查是否还有音频需要播放
      setTimeout(() => {
        if (audioQueueRef.current.length > 0) {
          playNextAudio()
        }
      }, 100)
    }
  }, [stopCurrentAudio, playAudioWithLipSync, getAudioContext])

  // 添加音频到队列并开始播放
  const queueAndPlayAudio = useCallback((audioData: string) => {
    console.log('添加音频到队列，当前队列长度:', audioQueueRef.current.length, '是否正在播放:', isPlayingRef.current)
    
    if (!audioData || audioData.length === 0) {
      console.warn('收到空的音频数据，跳过')
      return
    }
    
    // 直接使用函数式更新确保状态正确更新
    setAudioQueue(prev => {
      const newQueue = [...prev, audioData]
      console.log('更新后的队列长度:', newQueue.length)
      audioQueueRef.current = newQueue
      return newQueue
    })
    
    // 如果当前没有播放，则开始播放
    if (!isPlayingRef.current) {
      console.log('当前没有播放中的音频，开始播放队列')
      // 使用setTimeout确保状态更新后再调用
      setTimeout(() => {
        console.log('开始播放队列中的音频，当前队列长度:', audioQueueRef.current.length)
        if (audioQueueRef.current.length > 0) {
          playNextAudio().catch(err => console.error('播放音频失败:', err))
        }
      }, 50)
    } else {
      console.log('当前有音频正在播放，新音频已加入队列')
    }
  }, [playNextAudio])

  return (
    <AudioContext.Provider value={{ queueAndPlayAudio, resetAudioState }}>
      {children}
    </AudioContext.Provider>
  )
} 