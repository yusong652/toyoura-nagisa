import { useCallback } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message } from '@toyoura-nagisa/core'
import { chatService, sessionService } from '@toyoura-nagisa/core'

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
      // HttpClient unwraps ApiResponse, so we get ImageGenerateData directly
      // Errors are thrown as ApiBusinessError
      const result = await chatService.generateImage(sessionId)

      // Success - update messages if in current session
      if (sessionId === currentSessionId) {
        try {
          const historyData = await sessionService.getSessionHistory(sessionId)

          if (historyData.history && Array.isArray(historyData.history)) {
            const lastImageMessage = historyData.history
              .filter((msg: any) => msg.role === 'image')
              .pop()

            if (lastImageMessage) {
              const imageMessage: Message = {
                id: lastImageMessage.id || uuidv4(),
                role: 'assistant',
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

      return { success: true, image_path: result.image_path }
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