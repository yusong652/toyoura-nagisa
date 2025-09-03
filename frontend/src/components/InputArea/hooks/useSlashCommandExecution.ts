import { useState, useCallback } from 'react'
import { useChat } from '../../../contexts/chat/ChatContext'
import { useSession } from '../../../contexts/session/SessionContext'
import { SlashCommand, SlashCommandExecutionHookReturn } from '../types'

/**
 * Hook for handling slash command execution and loading states.
 * 
 * Separates command execution logic from the main InputArea component,
 * managing loading states for image and video generation commands.
 * 
 * Returns:
 *   - Loading states for different command types
 *   - Command execution function with proper error handling
 *   - Integration with ChatContext APIs
 */

export const useSlashCommandExecution = (): SlashCommandExecutionHookReturn => {
  // Loading state for slash commands
  const [isGeneratingImage, setIsGeneratingImage] = useState(false)
  const [isGeneratingVideo, setIsGeneratingVideo] = useState(false)
  
  // Get functions from ChatContext and SessionContext
  const { generateImage, generateVideo } = useChat()
  const { currentSessionId } = useSession()
  
  // Combined executing state
  const isExecuting = isGeneratingImage || isGeneratingVideo
  
  /**
   * Execute a slash command with proper error handling and loading states.
   * 
   * Args:
   *     command: SlashCommand - The command to execute
   *     args: string[] - Command arguments (currently unused)
   *     onComplete?: () => void - Callback to execute after command completion
   */
  const executeSlashCommand = useCallback(async (
    command: SlashCommand, 
    args: string[], 
    onComplete?: () => void
  ) => {
    console.log(`Executing command: ${command.trigger} with args:`, args)
    
    if (!currentSessionId) {
      console.error('No active session for slash command')
      return
    }
    
    try {
      if (command.trigger === 'image') {
        // Handle image generation command - generates based on conversation context
        setIsGeneratingImage(true)
        
        try {
          // Generate image based on recent conversation context
          const result = await generateImage(currentSessionId)
          if (!result.success) {
            console.error('Image generation failed:', result.error)
          }
        } finally {
          setIsGeneratingImage(false)
        }
      } else if (command.trigger === 'video') {
        // Handle video generation command - converts last image to video
        setIsGeneratingVideo(true)
        
        try {
          // Generate video from the last image in the conversation
          const result = await generateVideo(currentSessionId)
          if (!result.success) {
            console.error('Video generation failed:', result.error)
          }
        } finally {
          setIsGeneratingVideo(false)
        }
      }
      
      // Execute completion callback if provided
      onComplete?.()
    } catch (error) {
      console.error('Slash command execution failed:', error)
      // Reset loading states on error
      setIsGeneratingImage(false)
      setIsGeneratingVideo(false)
    }
  }, [currentSessionId, generateImage, generateVideo])
  
  return {
    isGeneratingImage,
    isGeneratingVideo,
    executeSlashCommand,
    isExecuting
  }
}