import { useState, useCallback, useMemo, useEffect } from 'react'
import { 
  SlashCommand, 
  SlashCommandContext, 
  SlashCommandMatch, 
  SlashCommandSuggestion,
  SlashCommandDetectionHookReturn,
  DEFAULT_INPUT_CONFIG 
} from '../types'

/**
 * Hook for slash command detection, parsing, and suggestion generation.
 * 
 * This hook provides comprehensive slash command detection functionality including:
 * - Real-time detection of '/' trigger character
 * - Command parsing with argument extraction  
 * - Intelligent command suggestions based on partial input
 * - Command matching and validation
 * - Cursor position tracking for accurate command positioning
 * 
 * The hook integrates seamlessly with the InputArea's message input
 * system while maintaining clean separation of concerns.
 * 
 * Architecture Benefits:
 * - Real-time command detection without performance impact
 * - Extensible command registration system
 * - Type-safe command handling with full TypeScript support
 * - Intelligent suggestion ranking based on relevance
 * - Proper cursor position management for inline commands
 * 
 * Args:
 *     message: string - Current input message text
 *     cursorPosition: number - Current textarea cursor position
 *     onCommandExecute?: (command: SlashCommand, args: string[]) => void | Promise<void>
 * 
 * Returns:
 *     SlashCommandDetectionHookReturn: Complete slash command detection state and handlers
 * 
 * TypeScript Learning Points:
 * - Advanced string parsing with regex patterns
 * - Context object composition for complex state
 * - Command pattern implementation with type safety
 * - Real-time suggestion algorithms with scoring
 * - Cursor position management in text inputs
 */


// Built-in commands for the system
export const BUILTIN_COMMANDS: SlashCommand[] = [
  {
    trigger: 'image',
    description: 'Generate image from conversation context',
    handler: async () => {
      // Handler is empty - actual execution happens in onCommandExecute
    },
    isVisible: true,
    category: 'media'
  },
  {
    trigger: 'video',
    description: 'Convert last image to video',
    handler: async () => {
      // Handler is empty - actual execution happens in onCommandExecute
    },
    isVisible: true,
    category: 'media'
  }
]

const useSlashCommandDetection = (
  message: string,
  cursorPosition: number,
  onCommandExecute?: (command: SlashCommand, args: string[]) => void | Promise<void>
): SlashCommandDetectionHookReturn => {
  
  // Activation state management
  const [isActivated, setIsActivated] = useState<boolean>(false)
  // After ESC, suppress auto-activation until the caret moves to just-after the first slash
  const [suppressSuggestions, setSuppressSuggestions] = useState<boolean>(false)
  const [prevCursorPosition, setPrevCursorPosition] = useState<number>(cursorPosition)
  
  // Available commands (builtin + user-defined)
  const availableCommands = useMemo(() => {
    return [...BUILTIN_COMMANDS, ...DEFAULT_INPUT_CONFIG.slashCommands.availableCommands]
  }, [])
  
  // Parse current command from message and cursor position
  const parseCurrentCommand = useCallback((
    text: string, 
    cursor: number
  ): SlashCommandMatch | null => {
    
    // Only trigger if slash is at position 0 and cursor is after it
    if (!text.startsWith('/') || cursor === 0) {
      return null
    }
    
    const slashIndex = 0
    
    // Extract command text from slash to cursor
    const commandText = text.substring(slashIndex + 1, cursor)
    
    // Check if we have a complete command
    const parts = commandText.split(' ')
    const commandName = parts[0]
    const args = parts.slice(1)
    
    // Find matching command
    const command = availableCommands.find(cmd => cmd.trigger === commandName)
    if (!command) return null
    
    return {
      command,
      args,
      fullMatch: `/${commandText}`,
      position: {
        start: slashIndex,
        end: cursor
      }
    }
    
  }, [availableCommands])
  
  // Generate command suggestions based on partial input
  const generateSuggestions = useCallback((
    text: string, 
    cursor: number,
    activated: boolean
  ): SlashCommandSuggestion[] => {
    
    // Only show suggestions if explicitly activated
    if (!activated || !text.startsWith('/') || cursor === 0) {
      return []
    }
    
    const slashIndex = 0
    
    // Extract partial command text
    const partialCommand = text.substring(slashIndex + 1, cursor).toLowerCase()
    
    // Find matching commands
    const suggestions: SlashCommandSuggestion[] = []
    
    for (const command of availableCommands) {
      if (!command.isVisible) continue
      
      const trigger = command.trigger.toLowerCase()
      let relevanceScore = 0
      
      // Empty partial command shows all commands
      if (partialCommand === '') {
        relevanceScore = 50
      }
      // Exact match gets highest score
      else if (trigger === partialCommand) {
        relevanceScore = 100
      }
      // Starts with partial command
      else if (trigger.startsWith(partialCommand)) {
        relevanceScore = 80 + (partialCommand.length / trigger.length) * 20
      }
      // Contains partial command
      else if (trigger.includes(partialCommand)) {
        relevanceScore = 40 + (partialCommand.length / trigger.length) * 20
      }
      
      if (relevanceScore > 0) {
        suggestions.push({
          command,
          relevanceScore,
          matchedText: partialCommand
        })
      }
    }
    
    // Sort by relevance score (highest first)
    return suggestions.sort((a, b) => b.relevanceScore - a.relevanceScore)
    
  }, [availableCommands])
  
  // Auto-activation logic: activate when user types '/' at beginning
  useEffect(() => {
    // Determine if re-arm condition is met: caret moved to position 1 (just after leading slash)
    const movedToAfterSlash = message.startsWith('/') && cursorPosition === 1 && prevCursorPosition !== 1

    // Clear suppression when:
    // - user moved caret to just-after the leading slash, or
    // - slash no longer at start (user edited text)
    if (suppressSuggestions) {
      if (movedToAfterSlash || !message.startsWith('/')) {
        setSuppressSuggestions(false)
      }
    }

    const shouldAutoActivate =
      message.startsWith('/') &&
      cursorPosition > 0 &&
      !suppressSuggestions &&
      DEFAULT_INPUT_CONFIG.slashCommands.enabled

    if (shouldAutoActivate && !isActivated) {
      setIsActivated(true)
    }

    // Track previous cursor for movement detection
    if (prevCursorPosition !== cursorPosition) {
      setPrevCursorPosition(cursorPosition)
    }
  }, [message, cursorPosition, isActivated, suppressSuggestions, prevCursorPosition])
  
  // Auto-deactivation: deactivate when slash is removed
  useEffect(() => {
    if (isActivated && !message.startsWith('/')) {
      setIsActivated(false)
    }
  }, [message, isActivated])
  
  // Current command context
  const context: SlashCommandContext = useMemo(() => {
    const isTriggered = isActivated && 
                       message.startsWith('/') && 
                       cursorPosition > 0 && 
                       DEFAULT_INPUT_CONFIG.slashCommands.enabled
    
    const suggestions = generateSuggestions(message, cursorPosition, isActivated)
    
    return {
      currentText: message,
      cursorPosition,
      availableCommands,
      isTriggered,
      suggestions
    }
  }, [message, cursorPosition, availableCommands, generateSuggestions, isActivated])
  
  // Active command match
  const activeCommand = useMemo(() => {
    if (!context.isTriggered) return null
    return parseCurrentCommand(message, cursorPosition)
  }, [context.isTriggered, message, cursorPosition, parseCurrentCommand])
  
  // Command execution handler
  const executeCommand = useCallback(async (command: SlashCommand, args: string[]) => {
    try {
      await command.handler(args)
      if (onCommandExecute) {
        await onCommandExecute(command, args)
      }
    } catch (error) {
      console.error(`Error executing command ${command.trigger}:`, error)
    }
  }, [onCommandExecute])
  
  // Select suggestion handler
  const selectSuggestion = useCallback((suggestion: SlashCommandSuggestion) => {
    // The parent component handles command execution
  }, [])
  
  // Clear active command - ESC handling: suppress re-activation until re-armed
  const clearCommand = useCallback(() => {
    if (isActivated) {
      setIsActivated(false)
      setSuppressSuggestions(true) // Prevent re-activation until re-armed
    }
  }, [isActivated])
  
  return {
    context,
    activeCommand,
    suggestions: context.suggestions,
    isCommandActive: context.isTriggered && context.suggestions.length > 0,
    executeCommand,
    selectSuggestion,
    clearCommand,
    availableCommands
  }
}

export default useSlashCommandDetection

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **Advanced String Parsing**:
 *    ```typescript
 *    for (let i = cursor - 1; i >= 0; i--) {
 *      const char = text[i]
 *      if (char === '/') {
 *        slashIndex = i
 *        break
 *      }
 *    }
 *    ```
 *    Manual character-by-character parsing with boundary detection
 * 
 * 2. **Command Pattern with TypeScript**:
 *    ```typescript
 *    interface SlashCommand {
 *      trigger: string
 *      handler: (args: string[]) => void | Promise<void>
 *    }
 *    ```
 *    Type-safe command pattern supporting both sync and async handlers
 * 
 * 3. **Scoring Algorithm Implementation**:
 *    ```typescript
 *    let relevanceScore = 0
 *    if (trigger === partialCommand) relevanceScore = 100
 *    else if (trigger.startsWith(partialCommand)) relevanceScore = 80
 *    ```
 *    Numerical scoring system for intelligent suggestion ranking
 * 
 * 4. **Complex Object Composition**:
 *    ```typescript
 *    const context: SlashCommandContext = useMemo(() => ({
 *      currentText: message,
 *      suggestions: generateSuggestions(message, cursorPosition)
 *    }), [dependencies])
 *    ```
 *    Computed context object combining multiple data sources
 * 
 * 5. **Cursor Position Management**:
 *    ```typescript
 *    const commandText = text.substring(slashIndex + 1, cursor)
 *    const position = { start: slashIndex, end: cursor }
 *    ```
 *    Precise text selection and cursor position tracking
 * 
 * 6. **Async Command Execution**:
 *    ```typescript
 *    const executeCommand = useCallback(async (command, args) => {
 *      await command.handler(args)
 *      if (onCommandExecute) await onCommandExecute(command, args)
 *    }, [onCommandExecute])
 *    ```
 *    Proper async/await handling with error catching
 * 
 * Architecture Benefits:
 * - **Real-time Processing**: Efficient parsing without blocking UI
 * - **Extensible Commands**: Easy to add new slash commands
 * - **Type Safety**: Full TypeScript coverage prevents runtime errors
 * - **Performance**: Optimized with useMemo and useCallback
 * - **Integration Ready**: Clean interface for InputArea integration
 * 
 * Usage in InputArea:
 * ```typescript
 * const { 
 *   isCommandActive, 
 *   suggestions, 
 *   executeCommand 
 * } = useSlashCommand(message, cursorPosition, handleCommandExecute)
 * 
 * // Show suggestions dropdown when command is active
 * {isCommandActive && suggestions.length > 0 && (
 *   <CommandSuggestions suggestions={suggestions} />
 * )}
 * ```
 * 
 * Future Extensions:
 * - Slash command autocomplete UI component
 * - Command history and favorites
 * - Custom command registration API
 * - Command validation and parameter checking
 * - Multi-step command flows
 * - Command templates and snippets
 */
