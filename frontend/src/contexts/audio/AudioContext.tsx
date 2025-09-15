import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect, useRef } from 'react'
import { startLipSync, stopLipSync, isLive2DModelInitialized } from '../../utils/live2d'
import { AudioQueueItem, AudioContextType } from '../../types/audio'

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
  // Use useRef instead of useState to store audioContext to avoid re-render issues
  const audioContextRef = useRef<AudioContext | null>(null)
  const [currentSource, setCurrentSource] = useState<AudioBufferSourceNode | null>(null)
  const [currentAnalyser, setCurrentAnalyser] = useState<AnalyserNode | null>(null)
  const [audioQueue, setAudioQueue] = useState<AudioQueueItem[]>([])
  const [isPlaying, setIsPlaying] = useState(false)
  const [audioContextInitialized, setAudioContextInitialized] = useState(false)
  const [currentAudioPromise, setCurrentAudioPromise] = useState<Promise<void> | null>(null)
  // Add ref to track queue state to avoid closure issues
  const audioQueueRef = useRef<AudioQueueItem[]>([])
  const isPlayingRef = useRef<boolean>(false)
  // Add ref to track whether current audio should be stopped
  const shouldStopCurrentAudioRef = useRef<boolean>(false)

  // Sync ref when audioQueue state updates
  useEffect(() => {
    audioQueueRef.current = audioQueue;
  }, [audioQueue]);

  // Sync ref when isPlaying state updates
  useEffect(() => {
    isPlayingRef.current = isPlaying;
  }, [isPlaying]);

  // Initialize AudioContext and ensure it's activated
  useEffect(() => {
    // Create silent audio to activate AudioContext
    const initializeAudioContext = async () => {
      if (!audioContextRef.current) {
        try {
          audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)()

          // Check AudioContext state
          if (audioContextRef.current.state === 'suspended') {
            // Create a brief silent audio to activate AudioContext
            const silentBuffer = audioContextRef.current.createBuffer(1, 1, 22050)
            const source = audioContextRef.current.createBufferSource()
            source.buffer = silentBuffer
            source.connect(audioContextRef.current.destination)
            source.start()

            // Try to resume AudioContext
            try {
              await audioContextRef.current.resume()
              setAudioContextInitialized(true)
            } catch (err) {
              console.error('Failed to resume AudioContext:', err)
            }
          } else {
            setAudioContextInitialized(true)
          }
        } catch (error) {
          console.error('Failed to initialize AudioContext:', error)
        }
      }
    }

    // Add user interaction event listeners to activate AudioContext
    const activateAudioContext = async () => {
      if (audioContextRef.current && audioContextRef.current.state === 'suspended') {
        try {
          await audioContextRef.current.resume()
          setAudioContextInitialized(true)
        } catch (err) {
          console.error('Failed to resume AudioContext after user interaction:', err)
        }
      }
    }

    // Initialize
    initializeAudioContext()

    // Add event listeners
    const events = ['click', 'touchstart', 'keydown']
    events.forEach(event => document.addEventListener(event, activateAudioContext, { once: true }))

    return () => {
      // Clean up event listeners
      events.forEach(event => document.removeEventListener(event, activateAudioContext))
    }
  }, [])

  // Get AudioContext and ensure it's activated
  const getAudioContext = useCallback(async () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)()
    }

    // If state is suspended, try to resume
    if (audioContextRef.current.state === 'suspended') {
      try {
        await audioContextRef.current.resume()
      } catch (err: any) {
        console.warn('Failed to resume AudioContext:', err)
      }
    }

    return audioContextRef.current
  }, [])

  // Stop currently playing audio
  const stopCurrentAudio = useCallback(async () => {
    // Mark that current audio should be stopped
    shouldStopCurrentAudioRef.current = true;

    if (currentSource) {
      try {
        currentSource.stop()
        currentSource.disconnect()
        if (currentAnalyser) {
          currentAnalyser.disconnect()
        }
        // Stop Live2D lip sync
        stopLipSync()
      } catch (e) {
        console.log('Audio already stopped')
      } finally {
        setCurrentSource(null)
        setCurrentAnalyser(null)
      }
    }

    // Reset flag
    shouldStopCurrentAudioRef.current = false;
  }, [currentSource, currentAnalyser])

  // Play single audio with lip sync
  const playAudioWithLipSync = useCallback((audioBase64: string): Promise<void> => {
    return new Promise(async (resolve, reject) => {
      try {
        // Reset stop flag
        shouldStopCurrentAudioRef.current = false;

        // Validate audio data
        if (!audioBase64 || audioBase64.length === 0) {
          console.warn('Received empty audio data, skipping playback')
          resolve()
          return
        }

        // Validate base64 format
        try {
          // Basic base64 format check
          if (!/^[A-Za-z0-9+/]*={0,2}$/.test(audioBase64)) {
            console.error('Invalid base64 format:', audioBase64.substring(0, 50) + '...')
            reject(new Error('Invalid base64 format'))
            return
          }
        } catch (e) {
          console.error('Base64 format validation failed:', e)
          reject(new Error('Base64 validation failed'))
          return
        }

        let audioBuffer: ArrayBuffer
        try {
          const binaryString = atob(audioBase64)

          if (binaryString.length === 0) {
            console.warn('Binary string empty after base64 decode')
            resolve()
            return
          }

          const uint8Array = Uint8Array.from(binaryString, c => c.charCodeAt(0))
          audioBuffer = uint8Array.buffer
        } catch (e) {
          console.error('Base64 decode failed:', e)
          reject(new Error('Base64 decode failed: ' + e))
          return
        }

        if (audioBuffer.byteLength === 0) {
          console.warn('Decoded audio data is empty, skipping playback')
          resolve()
          return
        }
        const context = await getAudioContext()

        // Ensure AudioContext is in running state
        if (context.state === 'suspended') {
          try {
            await context.resume()
          } catch (error) {
            console.warn('Failed to resume AudioContext:', error)
          }
        }

        // If marked for stopping before decoding, return directly
        if (shouldStopCurrentAudioRef.current) {
          resolve();
          return;
        }
        
        context.decodeAudioData(audioBuffer, (decodedData) => {
          try {
            // If marked for stopping after decoding, return directly
            if (shouldStopCurrentAudioRef.current) {
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

            // Check if Live2D is enabled (from localStorage) and model is initialized
            const isLive2DEnabled = localStorage.getItem('live2d-enabled') !== 'false'
            if (isLive2DEnabled && isLive2DModelInitialized()) {
              startLipSync(analyser)
            }

            // Create flag to track if audio has completed
            let audioCompleted = false;
            
            source.onended = () => {
              // Only handle if audio completed normally
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

            // AudioBufferSourceNode has no onerror event, use try-catch for error handling
            try {
              source.start(0)

              // Set safety timeout to ensure continuation even if onended doesn't trigger
              const safetyTimeout = setTimeout(() => {
                if (!audioCompleted && !shouldStopCurrentAudioRef.current) {
                  audioCompleted = true;
                  stopLipSync()
                  try {
                    source.stop()
                    source.disconnect()
                    analyser.disconnect()
                  } catch (e) {
                    // Ignore possible errors
                  }
                  setCurrentSource(null)
                  setCurrentAnalyser(null)
                  resolve()
                }
              }, (decodedData.duration * 1000) + 500); // Audio length + 500ms safety margin

              // Check for manual stop
              const checkStopInterval = setInterval(() => {
                if (shouldStopCurrentAudioRef.current && !audioCompleted) {
                  audioCompleted = true;
                  clearTimeout(safetyTimeout);
                  clearInterval(checkStopInterval);
                  stopLipSync();
                  try {
                    source.stop();
                    source.disconnect();
                    analyser.disconnect();
                  } catch (e) {
                    // Ignore possible errors
                  }
                  setCurrentSource(null);
                  setCurrentAnalyser(null);
                  resolve();
                }
              }, 100);
              
            } catch (error) {
              console.error('Failed to play audio:', error)
              stopLipSync()
              source.disconnect()
              analyser.disconnect()
              setCurrentSource(null)
              setCurrentAnalyser(null)
              reject(error)
            }
          } catch (error) {
            console.error('Failed to set up audio source:', error)
            stopLipSync()
            reject(error)
          }
        }, (err: Error) => {
          console.error('Audio decode failed:', err)
          console.error('Failed audio buffer size:', audioBuffer?.byteLength || 0, 'bytes')
          try {
            if (audioBuffer && audioBuffer.byteLength > 0) {
              console.error('First 100 bytes of audio data:', new Uint8Array(audioBuffer.slice(0, Math.min(100, audioBuffer.byteLength))))
            }
          } catch (bufferError) {
            console.error('Cannot read audio buffer data:', bufferError)
          }
          stopLipSync()
          reject(new Error('Audio decode failed: ' + err))
        })
      } catch (error) {
        console.error('Failed to process audio data:', error)
        stopLipSync()
        reject(error)
      }
    })
  }, [getAudioContext])

  // Play next audio in queue
  const playNextAudio = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) {
      return
    }

    setIsPlaying(true)
    isPlayingRef.current = true;

    const audioItem = audioQueueRef.current[0]

    // Update queue state
    setAudioQueue(prev => {
      const newQueue = prev.slice(1)
      return newQueue
    })

    try {
      // Ensure AudioContext is initialized and activated
      await getAudioContext()

      // Create new audio playback Promise
      const newAudioPromise = playAudioWithLipSync(audioItem.data)
      setCurrentAudioPromise(newAudioPromise)
      await newAudioPromise

      // Audio playback completed, call completion callback
      audioItem.onComplete();
    } catch (error) {
      console.error('Audio playback error:', error)
      // Call completion callback even on error to avoid blocking
      audioItem.onComplete();
    } finally {
      setIsPlaying(false)
      isPlayingRef.current = false;
      setCurrentAudioPromise(null)

      // Check if there are more audios to play using latest queue state
      setTimeout(() => {
        if (audioQueueRef.current.length > 0) {
          playNextAudio()
        }
      }, 100)
    }
  }, [getAudioContext, playAudioWithLipSync])

  // Reset audio state
  const resetAudioState = useCallback(async () => {
    // Cancel all audio Promises in queue
    audioQueueRef.current.forEach(item => {
      if (item.onComplete) {
        item.onComplete(); // Call completion callbacks for all waiting audios
      }
    });

    setAudioQueue([])
    audioQueueRef.current = [];
    await stopCurrentAudio()
    setIsPlaying(false)
    isPlayingRef.current = false;
    setCurrentAudioPromise(null)
  }, [stopCurrentAudio])

  // Add audio to queue and start playback
  const queueAndPlayAudio = useCallback((audioData: string): Promise<void> => {
    if (!audioData || audioData.length === 0) {
      console.warn('Received empty audio data, skipping')
      return Promise.resolve()
    }

    return new Promise<void>((resolve) => {
      // Create identifier to record current audio position in queue
      const currentQueueLength = audioQueueRef.current.length;

      // Use functional update to ensure correct state update
      setAudioQueue(prev => {
        const newQueue = [...prev, {
          data: audioData,
          onComplete: resolve // Store resolve callback to call when audio playback completes
        }]
        audioQueueRef.current = newQueue
        return newQueue
      })

      // If not currently playing, start playback
      if (!isPlayingRef.current) {
        // Use setTimeout to ensure state update before calling
        setTimeout(() => {
          if (audioQueueRef.current.length > 0) {
            playNextAudio().catch(err => console.error('Audio playback failed:', err))
          }
        }, 50)
      }
    });
  }, [playNextAudio])

  return (
    <AudioContext.Provider value={{ 
      queueAndPlayAudio, 
      resetAudioState
    }}>
      {children}
    </AudioContext.Provider>
  )
} 