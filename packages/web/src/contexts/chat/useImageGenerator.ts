import { useCallback } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message } from '@aiNagisa/core'
import { chatService, sessionService } from '@aiNagisa/core'

interface UseImageGeneratorProps {
  currentSessionId: string | null
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
}

interface ImageGeneratorResult {
  success: boolean
  image_path?: string
  error?: string
}

export const useImageGenerator = ({
  currentSessionId,
  setMessages
}: UseImageGeneratorProps) => {

  const generateImage = useCallback(async (
    sessionId: string
  ): Promise<ImageGeneratorResult> => {

    try {
      const result = await chatService.generateImage(sessionId)
      
      if (result.success && sessionId === currentSessionId) {
        try {
          const historyData = await sessionService.getSessionHistory(sessionId)
          
          if (historyData.history && Array.isArray(historyData.history)) {
            const lastImageMessage = historyData.history
              .filter((msg: any) => msg.role === 'image')
              .pop()

            if (lastImageMessage) {
              const imageMessage: Message = {
                id: lastImageMessage.id || uuidv4(),
                role: 'assistant',  // ✨ Use role instead of sender: 'bot'
                text: lastImageMessage.content || '',
                timestamp: new Date(lastImageMessage.timestamp || Date.now()).getTime(),
                files: [{
                  name: 'generated_image',
                  type: 'image/png',
                  data: `/api/images/${lastImageMessage.image_path}`
                }]
              }

              setMessages(prev => [...prev, imageMessage])
            }
          }
        } catch (error) {
          console.error('获取生成的图片消息失败:', error)
        }
      }
      
      return result
    } catch (error) {
      console.error('图片生成失败:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : '图片生成失败'
      }
    }
  }, [currentSessionId, setMessages])

  return {
    generateImage
  }
}