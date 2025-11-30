import { useRef, useCallback } from 'react'
import { FileData } from '@toyoura-nagisa/core'
import { 
  FileHandlingHookReturn, 
  validateFileSize, 
  generateFileName,
  DEFAULT_INPUT_CONFIG,
  FileProcessingOptions 
} from '../types'

/**
 * Custom hook for comprehensive file handling in input area.
 * 
 * This hook encapsulates all file-related operations including file selection,
 * paste handling, file processing, and validation. It follows aiNagisa's
 * clean architecture by isolating file handling concerns from UI rendering.
 * 
 * Features:
 * - File input element management with ref
 * - File selection from file picker dialog
 * - Paste image handling from clipboard
 * - File validation and processing pipeline
 * - File removal with index-based operations
 * - File limit enforcement and feedback
 * 
 * Args:
 *     files: FileData[] - Current files array from state
 *     setFiles: Function to update files array
 *     maxFiles?: number - Maximum number of files allowed
 *     processingOptions?: FileProcessingOptions - File processing configuration
 * 
 * Returns:
 *     FileHandlingHookReturn: Complete file handling interface:
 *         - fileInputRef: React ref for hidden file input element
 *         - handleFileSelect: Handler for file input change events
 *         - handlePaste: Handler for paste events with image detection
 *         - removeFile: Function to remove file by index
 *         - openFileSelector: Function to programmatically open file picker
 *         - canAddMoreFiles: boolean indicating if more files can be added
 *         - processFiles: Function to convert File objects to FileData
 * 
 * TypeScript Learning Points:
 * - useRef with HTMLInputElement typing
 * - useCallback for event handler optimization
 * - Promise.all for concurrent async operations
 * - FileReader API with proper typing
 * - Error handling with try-catch in async contexts
 */
const useFileHandling = (
  files: FileData[],
  setFiles: (files: FileData[] | ((prev: FileData[]) => FileData[])) => void,
  maxFiles: number = DEFAULT_INPUT_CONFIG.maxFiles,
  processingOptions: FileProcessingOptions = DEFAULT_INPUT_CONFIG.fileHandling
): FileHandlingHookReturn => {
  // File input reference for programmatic access
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  // Check if more files can be added
  const canAddMoreFiles = files.length < maxFiles
  
  // Process File objects into FileData format
  const processFiles = useCallback(async (fileList: File[]): Promise<FileData[]> => {
    const validFiles = fileList.filter(file => {
      const validation = validateFileSize(file)
      if (!validation.valid) {
        console.warn(`File ${file.name} rejected: ${validation.error}`)
        return false
      }
      return true
    })
    
    // Process files concurrently for better performance
    const processedFiles = await Promise.all(
      validFiles.map(file => {
        return new Promise<FileData>((resolve, reject) => {
          const reader = new FileReader()
          
          reader.onload = (e) => {
            const result = e.target?.result
            if (typeof result === 'string') {
              resolve({
                name: file.name,
                type: file.type,
                data: result
              })
            } else {
              reject(new Error(`Failed to read file: ${file.name}`))
            }
          }
          
          reader.onerror = () => {
            reject(new Error(`Failed to read file: ${file.name}`))
          }
          
          reader.readAsDataURL(file)
        })
      })
    )
    
    return processedFiles
  }, [])
  
  // Handle file selection from file input
  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files
    if (!selectedFiles || selectedFiles.length === 0) return
    
    // Calculate how many files we can actually add
    const remainingSlots = maxFiles - files.length
    const filesToProcess = Array.from(selectedFiles).slice(0, remainingSlots)
    
    try {
      const newFileData = await processFiles(filesToProcess)
      
      setFiles(prevFiles => {
        const combined = [...prevFiles, ...newFileData]
        // Ensure we don't exceed maxFiles limit
        return combined.slice(0, maxFiles)
      })
      
      // Clear the input so the same file can be selected again if needed
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
      
      // Warn if some files were not processed due to limit
      if (selectedFiles.length > filesToProcess.length) {
        console.warn(`Only ${filesToProcess.length} of ${selectedFiles.length} files added due to limit`)
      }
      
    } catch (error) {
      console.error('Error processing selected files:', error)
    }
  }, [files.length, maxFiles, processFiles, setFiles])
  
  // Handle paste events for image files
  const handlePaste = useCallback(async (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items
    if (!items || !canAddMoreFiles) return
    
    // Look for image items in clipboard
    const imageFiles: File[] = []
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.startsWith('image/')) {
        const file = items[i].getAsFile()
        if (file) {
          imageFiles.push(file)
        }
      }
    }
    
    if (imageFiles.length === 0) return
    
    try {
      // Process pasted images with generated names
      const filesWithNames = imageFiles.map(file => {
        // Generate name for pasted images
        const name = generateFileName(`pasted-image-${Date.now()}.png`, file.type)
        return new File([file], name, { type: file.type })
      })
      
      const newFileData = await processFiles(filesWithNames)
      
      setFiles(prevFiles => {
        const combined = [...prevFiles, ...newFileData]
        return combined.slice(0, maxFiles)
      })
      
    } catch (error) {
      console.error('Error processing pasted files:', error)
    }
  }, [canAddMoreFiles, maxFiles, processFiles, setFiles])
  
  // Remove file by index
  const removeFile = useCallback((index: number) => {
    setFiles(prevFiles => prevFiles.filter((_, i) => i !== index))
  }, [setFiles])
  
  // Open file selector programmatically
  const openFileSelector = useCallback(() => {
    if (canAddMoreFiles && fileInputRef.current) {
      fileInputRef.current.click()
    }
  }, [canAddMoreFiles])
  
  return {
    fileInputRef,
    handleFileSelect,
    handlePaste,
    removeFile,
    openFileSelector,
    canAddMoreFiles,
    processFiles
  }
}

export default useFileHandling

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **useRef with Specific Element Type**:
 *    ```typescript
 *    const fileInputRef = useRef<HTMLInputElement>(null)
 *    ```
 *    Typed ref provides access to HTMLInputElement-specific properties
 * 
 * 2. **useCallback with Event Handler Types**:
 *    ```typescript
 *    const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
 *      // Handler logic with proper event typing
 *    }, [files.length, maxFiles, processFiles, setFiles])
 *    ```
 *    Event handlers properly typed with React synthetic event types
 * 
 * 3. **Promise.all with Generic Type Inference**:
 *    ```typescript
 *    const processedFiles = await Promise.all(
 *      validFiles.map(file => {
 *        return new Promise<FileData>((resolve, reject) => {
 *          // Async processing with explicit return type
 *        })
 *      })
 *    )
 *    ```
 *    Promise handling with explicit generic types for type safety
 * 
 * 4. **FileReader API with Type Guards**:
 *    ```typescript
 *    if (typeof result === 'string') {
 *      resolve({ name: file.name, type: file.type, data: result })
 *    }
 *    ```
 *    Runtime type checking for FileReader result handling
 * 
 * 5. **Functional State Updates**:
 *    ```typescript
 *    setFiles(prevFiles => {
 *      const combined = [...prevFiles, ...newFileData]
 *      return combined.slice(0, maxFiles)
 *    })
 *    ```
 *    Functional updates ensure proper React state handling
 * 
 * 6. **Error Handling in Async Contexts**:
 *    Try-catch blocks in async callbacks with proper error typing
 * 
 * Hook Architecture Benefits:
 * - **Single Responsibility**: Only handles file operations
 * - **Async Operation Management**: Proper handling of file reading
 * - **Error Resilience**: Graceful handling of file processing errors
 * - **Performance Optimized**: useCallback prevents unnecessary re-renders
 * - **Type Safety**: Complete typing prevents file handling bugs
 * - **User Experience**: Provides feedback and limits enforcement
 * 
 * File Processing Pipeline:
 * 1. File validation (size, type checking)
 * 2. Concurrent processing with Promise.all
 * 3. FileReader async operation handling
 * 4. State update with functional pattern
 * 5. Error handling and user feedback
 * 
 * Integration Pattern:
 * ```typescript
 * const {
 *   fileInputRef,
 *   handleFileSelect,
 *   handlePaste,
 *   removeFile,
 *   openFileSelector
 * } = useFileHandling(files, setFiles, maxFiles)
 * ```
 * 
 * This pattern encapsulates all file complexity, making the main component
 * focus on UI orchestration rather than file processing details.
 */