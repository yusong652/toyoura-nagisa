import { useState, useMemo } from 'react'
import { useChat } from '../../../contexts/chat/ChatContext'
import { FileData } from '../../../types/chat'
import { 
  InputStateHookReturn, 
  MessageInputInfo, 
  calculateMessageInfo,
  DEFAULT_INPUT_CONFIG 
} from '../types'

/**
 * Custom hook for managing input area state.
 * 
 * This hook centralizes all state management for the input area including
 * message text, files array, and derived state calculations. It follows
 * aiNagisa's clean architecture by separating state concerns from UI logic.
 * 
 * Features:
 * - Message text state with validation
 * - File collection state management
 * - Derived state calculations (hasContent, isEmpty, etc.)
 * - Integration with ChatContext for loading state
 * - Clear input functionality for post-send cleanup
 * 
 * Args:
 *     initialMessage?: string - Optional initial message content
 *     maxFiles?: number - Maximum number of files allowed
 * 
 * Returns:
 *     InputStateHookReturn: Complete state management interface:
 *         - message: string - Current message text
 *         - setMessage: Function to update message text
 *         - files: FileData[] - Current file collection
 *         - setFiles: Function to update files (supports functional updates)
 *         - clearInput: Function to reset both message and files
 *         - messageInfo: MessageInputInfo - Derived state calculations
 *         - isInputDisabled: boolean - Whether input should be disabled
 * 
 * TypeScript Learning Points:
 * - useState with explicit generic typing for complex state
 * - useMemo for expensive derived state calculations
 * - Functional state updates with proper typing
 * - Custom hook return type interface design
 * - Context integration with proper error handling
 */
const useInputState = (
  initialMessage: string = '',
  maxFiles: number = DEFAULT_INPUT_CONFIG.maxFiles
): InputStateHookReturn => {
  // Core state management
  const [message, setMessage] = useState<string>(initialMessage)
  const [files, setFiles] = useState<FileData[]>([])
  
  // External state from chat context
  const { isLoading } = useChat()
  
  // Clear all input state
  const clearInput = () => {
    setMessage('')
    setFiles([])
  }
  
  // Derived state calculations (memoized for performance)
  const messageInfo = useMemo<MessageInputInfo>(() => 
    calculateMessageInfo(message, files),
    [message, files]
  )
  
  // Input disabled state (based on chat loading or file limits)
  const isInputDisabled = useMemo<boolean>(() => 
    isLoading || files.length >= maxFiles,
    [isLoading, files.length, maxFiles]
  )
  
  return {
    message,
    setMessage,
    files,
    setFiles,
    clearInput,
    messageInfo,
    isInputDisabled
  }
}

export default useInputState

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **Generic useState with Complex Types**:
 *    ```typescript
 *    const [files, setFiles] = useState<FileData[]>([])
 *    ```
 *    Explicit generic typing ensures type safety for complex arrays
 * 
 * 2. **Functional State Updates Support**:
 *    ```typescript
 *    setFiles: (files: FileData[] | ((prev: FileData[]) => FileData[])) => void
 *    ```
 *    Return type supports both direct values and functional updates
 * 
 * 3. **useMemo with Explicit Type Annotation**:
 *    ```typescript
 *    const messageInfo = useMemo<MessageInputInfo>(() => 
 *      calculateMessageInfo(message, files),
 *      [message, files]
 *    )
 *    ```
 *    Explicit typing prevents type inference issues and provides clarity
 * 
 * 4. **Derived State Pattern**:
 *    Computing complex state from simple primitives using pure functions
 * 
 * 5. **Context Integration**:
 *    Properly typed context hook usage with error handling
 * 
 * 6. **Default Parameters with Config**:
 *    Using configuration constants for default values
 * 
 * Hook Design Benefits:
 * - **Single Responsibility**: Only handles input state management
 * - **Testability**: Easy to unit test state transformations
 * - **Reusability**: Can be used in other input components
 * - **Performance**: Memoized calculations prevent unnecessary re-renders
 * - **Type Safety**: Complete TypeScript coverage prevents runtime errors
 * 
 * Usage Pattern:
 * ```typescript
 * const {
 *   message,
 *   setMessage, 
 *   files,
 *   messageInfo,
 *   clearInput
 * } = useInputState()
 * ```
 * 
 * This pattern separates state management from UI rendering, making the
 * main component cleaner and more focused on orchestration rather than
 * state manipulation details.
 */