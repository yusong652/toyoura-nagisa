import { useState, useCallback, useMemo, useEffect } from 'react'
import { 
  SlashCommand, 
  SlashCommandContext, 
  SlashCommandMatch, 
  SlashCommandSuggestion,
  DEFAULT_INPUT_CONFIG 
} from '../types'

/**
 * Hook for slash command detection, parsing, and execution.
 * 
 * This hook provides comprehensive slash command functionality including:
 * - Real-time detection of '/' trigger character
 * - Command parsing with argument extraction  
 * - Intelligent command suggestions based on partial input
 * - Command execution with proper context management
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
 *     SlashCommandHookReturn: Complete slash command state and handlers
 * 
 * TypeScript Learning Points:
 * - Advanced string parsing with regex patterns
 * - Context object composition for complex state
 * - Command pattern implementation with type safety
 * - Real-time suggestion algorithms with scoring
 * - Cursor position management in text inputs
 */

export interface SlashCommandHookReturn {
  context: SlashCommandContext
  activeCommand: SlashCommandMatch | null
  suggestions: SlashCommandSuggestion[]
  isCommandActive: boolean
  executeCommand: (command: SlashCommand, args: string[]) => Promise<void>
  selectSuggestion: (suggestion: SlashCommandSuggestion) => void
  clearCommand: () => void
  availableCommands: SlashCommand[]
}

// Built-in commands for the system
const BUILTIN_COMMANDS: SlashCommand[] = [
  {
    trigger: 'text_to_image',
    description: 'Generate an image from text description',
    handler: async (args: string[]) => {
      console.log('Executing text_to_image command with args:', args)
      // Implementation will be added when integrating with backend
    },
    isVisible: true,
    category: 'media'
  },
  {
    trigger: 'help',
    description: 'Show available commands and their usage',
    handler: async (args: string[]) => {
      console.log('Showing help for commands')
    },
    isVisible: true,
    category: 'utility'
  }
]

const useSlashCommand = (
  message: string,
  cursorPosition: number,
  onCommandExecute?: (command: SlashCommand, args: string[]) => void | Promise<void>
): SlashCommandHookReturn => {
  
  // Available commands (builtin + user-defined)
  const availableCommands = useMemo(() => {
    return [...BUILTIN_COMMANDS, ...DEFAULT_INPUT_CONFIG.slashCommands.availableCommands]
  }, [])
  
  // Parse current command from message and cursor position
  const parseCurrentCommand = useCallback((
    text: string, 
    cursor: number
  ): SlashCommandMatch | null => {
    
    // Find slash character before cursor position
    let slashIndex = -1
    for (let i = cursor - 1; i >= 0; i--) {
      const char = text[i]
      if (char === '/') {
        slashIndex = i
        break
      }
      if (char === ' ' || char === '\n') {
        // Stop if we hit whitespace before finding slash
        break
      }
    }
    
    if (slashIndex === -1) return null
    
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
    cursor: number
  ): SlashCommandSuggestion[] => {
    
    // Find slash character before cursor
    let slashIndex = -1
    for (let i = cursor - 1; i >= 0; i--) {
      const char = text[i]
      if (char === '/') {
        slashIndex = i
        break
      }
      if (char === ' ' || char === '\n') {
        break
      }
    }
    
    if (slashIndex === -1) return []
    
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
  
  // Current command context
  const context: SlashCommandContext = useMemo(() => {
    const isTriggered = message.includes('/') && 
                       cursorPosition > 0 && 
                       DEFAULT_INPUT_CONFIG.slashCommands.enabled
    
    const suggestions = isTriggered ? generateSuggestions(message, cursorPosition) : []
    
    return {
      currentText: message,
      cursorPosition,
      availableCommands,
      isTriggered,
      suggestions
    }
  }, [message, cursorPosition, availableCommands, generateSuggestions])
  
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
    // This will be implemented when integrating with message input
    console.log('Selecting suggestion:', suggestion.command.trigger)
    // For now, we'll return the selected command trigger
    // The actual text replacement should be handled by the parent component
  }, [])
  
  // Clear active command
  const clearCommand = useCallback(() => {
    // Reset command state - implementation depends on integration
    console.log('Clearing active command')
  }, [])
  
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

export default useSlashCommand

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