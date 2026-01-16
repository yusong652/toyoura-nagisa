/**
 * InputArea TypeScript type definitions.
 * 
 * Comprehensive type system for the input area component following
 * toyoura-nagisa's clean architecture principles with clear separation
 * between state, events, and component interfaces.
 * 
 * Architecture Benefits:
 * - Type-safe prop threading between hooks and components
 * - Clear contracts for each responsibility area
 * - Consistent with other toyoura-nagisa component patterns
 */

import { FileData } from '@toyoura-nagisa/core'

// =============================================================================
// Core Component Types
// =============================================================================

export interface InputAreaProps {
  className?: string
  placeholder?: string
  disabled?: boolean
  maxFiles?: number
  acceptedFileTypes?: string[]
}

export interface MessageInputInfo {
  content: string
  files: FileData[]
  hasContent: boolean
  isEmpty: boolean
  characterCount: number
}

// =============================================================================
// Hook Return Types
// =============================================================================

export interface InputStateHookReturn {
  message: string
  setMessage: (message: string) => void
  files: FileData[]
  setFiles: (files: FileData[] | ((prev: FileData[]) => FileData[])) => void
  clearInput: () => void
  messageInfo: MessageInputInfo
  isInputDisabled: boolean
}

export interface FileHandlingHookReturn {
  fileInputRef: React.RefObject<HTMLInputElement>
  handleFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void
  handlePaste: (e: React.ClipboardEvent) => void
  removeFile: (index: number) => void
  openFileSelector: () => void
  canAddMoreFiles: boolean
  processFiles: (files: File[]) => Promise<FileData[]>
}

export interface MessageSendingHookReturn {
  handleSendMessage: () => Promise<void>
  handleKeyPress: (e: React.KeyboardEvent) => Promise<void>
  canSendMessage: boolean
  isSending: boolean
  sendingStatus: SendingStatus
}

export interface InputAutoResizeHookReturn {
  textareaRef: React.RefObject<HTMLTextAreaElement>
  handleTextareaResize: () => void
  resetTextareaHeight: () => void
  maxHeight: number
}

// =============================================================================
// Component-Specific Types
// =============================================================================

export interface FilePreviewAreaProps {
  files: FileData[]
  onRemoveFile: (index: number) => void
  className?: string
  maxDisplayFiles?: number
}

export interface MessageInputProps {
  value: string
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void
  onKeyPress: (e: React.KeyboardEvent) => Promise<void>
  onKeyDown?: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void
  onPaste: (e: React.ClipboardEvent) => void
  placeholder?: string
  disabled?: boolean
  className?: string
  textareaRef: React.RefObject<HTMLTextAreaElement>
  autoFocus?: boolean
}

export interface InputControlsProps {
  onSendMessage: () => Promise<void>
  onFileSelect: () => void
  canSendMessage: boolean
  isSending: boolean
  className?: string
  showFileButton?: boolean
  showToolbar?: boolean
}

export interface FilePreviewItemProps {
  file: FileData
  index: number
  onRemove: (index: number) => void
  className?: string
}

// =============================================================================
// Utility Types
// =============================================================================

export interface SendingStatus {
  status: 'idle' | 'preparing' | 'sending' | 'success' | 'error'
  message?: string
}

export interface InputValidation {
  isValid: boolean
  errors: string[]
  warnings: string[]
}

export interface FileProcessingOptions {
  maxFileSize: number
  allowedTypes: string[]
  imageCompression?: boolean
  generateThumbnails?: boolean
}

export interface KeyboardShortcut {
  key: string
  ctrlKey?: boolean
  shiftKey?: boolean
  altKey?: boolean
  handler: (e: KeyboardEvent) => void | Promise<void>
  description: string
}

export interface DragDropState {
  isDragOver: boolean
  draggedFiles: File[]
  validDrop: boolean
}

// =============================================================================
// Event Handler Types
// =============================================================================

export type MessageChangeHandler = (e: React.ChangeEvent<HTMLTextAreaElement>) => void
export type KeyPressHandler = (e: React.KeyboardEvent) => Promise<void>
export type FileSelectHandler = (e: React.ChangeEvent<HTMLInputElement>) => void
export type PasteHandler = (e: React.ClipboardEvent) => void
export type FileRemoveHandler = (index: number) => void
export type SendMessageHandler = () => Promise<void>
export type DragDropHandler = (e: React.DragEvent) => void

// =============================================================================
// Configuration Types
// =============================================================================

export interface InputAreaConfig {
  maxMessageLength: number
  maxFiles: number
  maxFileSize: number
  allowedFileTypes: string[]
  autoResize: {
    enabled: boolean
    maxHeight: number
    minHeight: number
  }
  keyboard: {
    sendOnEnter: boolean
    newlineOnShiftEnter: boolean
  }
  fileHandling: FileProcessingOptions
  dragDrop: {
    enabled: boolean
    acceptMultiple: boolean
    visualFeedback: boolean
  }
}

// =============================================================================
// Constants
// =============================================================================

export const DEFAULT_INPUT_CONFIG: InputAreaConfig = {
  maxMessageLength: 10000,
  maxFiles: 10,
  maxFileSize: 50 * 1024 * 1024, // 50MB
  allowedFileTypes: ['*'],
  autoResize: {
    enabled: true,
    maxHeight: 300,
    minHeight: 84
  },
  keyboard: {
    sendOnEnter: true,
    newlineOnShiftEnter: true
  },
  fileHandling: {
    maxFileSize: 50 * 1024 * 1024,
    allowedTypes: ['*'],
    imageCompression: false,
    generateThumbnails: true
  },
  dragDrop: {
    enabled: true,
    acceptMultiple: true,
    visualFeedback: true
  }
}

export const SUPPORTED_IMAGE_TYPES = [
  'image/jpeg',
  'image/png', 
  'image/gif',
  'image/webp',
  'image/svg+xml',
  'image/bmp'
] as const

export const SUPPORTED_DOCUMENT_TYPES = [
  'application/pdf',
  'text/plain',
  'text/markdown',
  'application/json'
] as const

export const FILE_SIZE_LIMITS = {
  image: 10 * 1024 * 1024,    // 10MB
  document: 50 * 1024 * 1024, // 50MB
  other: 100 * 1024 * 1024    // 100MB
} as const

// =============================================================================
// Type Guards and Utilities
// =============================================================================

export const isImageFile = (file: FileData | File): boolean => {
  const type = file.type
  return SUPPORTED_IMAGE_TYPES.includes(type as any)
}

export const isDocumentFile = (file: FileData | File): boolean => {
  const type = file.type
  return SUPPORTED_DOCUMENT_TYPES.includes(type as any)
}

export const getFileCategory = (file: FileData | File): 'image' | 'document' | 'other' => {
  if (isImageFile(file)) return 'image'
  if (isDocumentFile(file)) return 'document'
  return 'other'
}

export const validateFileSize = (file: File): { valid: boolean; error?: string } => {
  const category = getFileCategory(file)
  const limit = FILE_SIZE_LIMITS[category]
  
  if (file.size > limit) {
    return {
      valid: false,
      error: `File too large. Max size for ${category} files: ${(limit / 1024 / 1024).toFixed(1)}MB`
    }
  }
  
  return { valid: true }
}

export const generateFileName = (originalName?: string, type?: string): string => {
  const timestamp = Date.now()
  const extension = type ? `.${type.split('/')[1]}` : ''
  return originalName || `file-${timestamp}${extension}`
}

export const isValidMessageContent = (content: string, maxLength: number = DEFAULT_INPUT_CONFIG.maxMessageLength): boolean => {
  return content.trim().length > 0 && content.length <= maxLength
}

export const calculateMessageInfo = (message: string, files: FileData[]): MessageInputInfo => {
  return {
    content: message,
    files,
    hasContent: message.trim().length > 0 || files.length > 0,
    isEmpty: message.trim().length === 0 && files.length === 0,
    characterCount: message.length
  }
}

/**
 * TypeScript Learning Points Demonstrated:
 * 
 * 1. **Comprehensive Interface Design**:
 *    Clear separation between component props, hook returns, and utility types
 * 
 * 2. **Generic Type Constraints**:
 *    Using const assertions and template literal types for type safety
 * 
 * 3. **Discriminated Unions**:
 *    SendingStatus uses union types for different states
 * 
 * 4. **Type Guards and Utilities**:
 *    Runtime type checking functions with proper return type narrowing
 * 
 * 5. **Configuration Objects**:
 *    Complex nested configuration with sensible defaults
 * 
 * 6. **Event Handler Types**:
 *    Specific typing for all React event handlers used
 *
 * 7. **Const Assertions**:
 *    Using 'as const' for literal type preservation
 * 
 * Architecture Benefits:
 * - **Type Safety**: Complete coverage prevents runtime errors
 * - **Extensibility**: Easy to add new features as the input evolves
 * - **Documentation**: Types serve as comprehensive documentation
 * - **IDE Support**: Full autocomplete and error checking
 * - **Refactoring Safety**: Changes caught at compile time
 * - **Team Collaboration**: Clear contracts between developers
 */

// =============================================================================
// File Mention Types (@ mention functionality)
// =============================================================================

/**
 * File search result from backend API
 */
export interface FileSearchResult {
  path: string           // Relative path from workspace
  filename: string       // File name only
  score: number          // Relevance score (0-100)
}

/**
 * File search API data (unwrapped from ApiResponse)
 */
export interface FileSearchData {
  query: string
  workspace: string
  results: FileSearchResult[]
  total: number
}

/**
 * File search API response (2025 Standard ApiResponse format)
 */
export interface FileSearchResponse {
  success: boolean
  message: string
  data: FileSearchData | null
  error_code: string | null
}

/**
 * Matched file mention in the input text
 */
export interface FileMentionMatch {
  file: FileSearchResult
  fullMatch: string       // e.g., "@test_files/sample.py"
  position: {
    start: number         // Position of @ character
    end: number           // Position after file path
  }
}

/**
 * File suggestion with relevance scoring
 */
export interface FileMentionSuggestion {
  file: FileSearchResult
  relevanceScore: number
  matchedText: string
}

/**
 * File mention detection context
 */
export interface FileMentionContext {
  currentText: string
  cursorPosition: number
  isTriggered: boolean
  query: string           // Search query after @
  suggestions: FileMentionSuggestion[]
}

/**
 * Hook return type for useFileMentionDetection
 */
export interface FileMentionDetectionHookReturn {
  context: FileMentionContext
  activeMention: FileMentionMatch | null
  suggestions: FileMentionSuggestion[]
  isMentionActive: boolean
  selectSuggestion: (suggestion: FileMentionSuggestion) => void
  clearMention: () => void
  isSearching: boolean
}

/**
 * Hook return type for useFileSearch
 */
export interface FileSearchHookReturn {
  searchFiles: (query: string) => Promise<FileSearchResult[]>
  results: FileSearchResult[]
  isSearching: boolean
  error: string | null
  clearResults: () => void
}
