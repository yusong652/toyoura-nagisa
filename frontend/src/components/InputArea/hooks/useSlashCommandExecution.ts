import { useState, useCallback } from 'react'
import { useChat } from '../../../contexts/chat/ChatContext'
import { useSession } from '../../../contexts/session/SessionContext'
import { SlashCommand, SlashCommandExecutionHookReturn, CommandExecutionTask } from '../types'

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
  // Command execution queue
  const [executionQueue, setExecutionQueue] = useState<CommandExecutionTask[]>([])
  
  // Get functions from ChatContext and SessionContext
  const { generateImage, generateVideo } = useChat()
  const { currentSessionId } = useSession()
  
  // Computed states based on queue
  const isGeneratingImage = executionQueue.some(task => 
    task.command.trigger === 'image' && task.status === 'executing'
  )
  const isGeneratingVideo = executionQueue.some(task => 
    task.command.trigger === 'video' && task.status === 'executing'
  )
  const isExecuting = executionQueue.some(task => task.status === 'executing')
  
  /**
   * Execute a slash command with proper error handling and queue management.
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
  ): Promise<{ success: boolean; error?: string }> => {
    console.log(`Executing command: ${command.trigger} with args:`, args)
    
    if (!currentSessionId) {
      console.error('No active session for slash command')
      return { success: false, error: 'No active session' }
    }
    
    // Create task and add to queue
    const taskId = `${command.trigger}-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`
    const task: CommandExecutionTask = {
      id: taskId,
      command,
      args,
      startTime: Date.now(),
      status: 'executing'
    }
    
    // Add task to queue
    setExecutionQueue(prev => [...prev, task])
    
    try {
      let result: { success: boolean; error?: string } = { success: false }
      
      if (command.trigger === 'image') {
        // Generate image based on recent conversation context
        result = await generateImage(currentSessionId)
      } else if (command.trigger === 'video') {
        // Generate video from the last image in the conversation
        result = await generateVideo(currentSessionId)
      }
      
      // Update task status
      setExecutionQueue(prev => prev.map(t =>
        t.id === taskId
          ? { ...t, status: result.success ? 'completed' : 'error', error: result.success ? undefined : result.error }
          : t
      ))
      
      if (!result.success) {
        console.error(`${command.trigger} generation failed:`, result.error)
      }
      
      // Execute completion callback if provided
      onComplete?.()
      
      // Remove completed task after a short delay to show completion
      setTimeout(() => {
        setExecutionQueue(prev => prev.filter(t => t.id !== taskId))
      }, 2000)
      
      return result
    } catch (error) {
      console.error('Slash command execution failed:', error)
      
      // Mark task as error
      const message = error instanceof Error ? error.message : 'Command execution failed'
      setExecutionQueue(prev => prev.map(t =>
        t.id === taskId
          ? { ...t, status: 'error', error: message }
          : t
      ))
      
      // Remove errored task after delay
      setTimeout(() => {
        setExecutionQueue(prev => prev.filter(t => t.id !== taskId))
      }, 3000)

      return { success: false, error: message }
    }
  }, [currentSessionId, generateImage, generateVideo])
  
  return {
    isGeneratingImage,
    isGeneratingVideo,
    executeSlashCommand,
    isExecuting,
    executionQueue: executionQueue.filter(task => task.status !== 'completed')
  }
}
