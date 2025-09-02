import React from 'react'
import { FilePreviewAreaProps, FilePreviewItemProps, isImageFile } from '../types'

/**
 * File preview item component for individual file display.
 * 
 * Displays a single file with appropriate preview (image thumbnail or file icon)
 * and provides removal functionality. This component is reusable and focused
 * on single-file rendering concerns.
 * 
 * Features:
 * - Image thumbnail display for image files
 * - Generic file icon for non-image files
 * - Remove button with hover effects
 * - File name truncation for long names
 * - Accessible markup with proper ARIA labels
 * 
 * Args:
 *     file: FileData - The file object to display
 *     index: number - File index for removal operations
 *     onRemove: Function to handle file removal
 *     className?: string - Optional CSS class for customization
 * 
 * Returns:
 *     JSX.Element: Complete file preview item with thumbnail and remove button
 * 
 * TypeScript Learning Points:
 * - Component composition with focused responsibility
 * - Props interface with required and optional fields
 * - Type guard usage for conditional rendering
 * - Event handler prop typing with specific signatures
 */
const FilePreviewItem: React.FC<FilePreviewItemProps> = ({ 
  file, 
  index, 
  onRemove, 
  className = '' 
}) => {
  const handleRemove = () => onRemove(index)
  
  return (
    <div className={`file-thumb-box ${className}`.trim()}>
      <button 
        className="file-thumb-del" 
        onClick={handleRemove}
        title={`Remove ${file.name}`}
        type="button"
        aria-label={`Remove file ${file.name}`}
      >
        ×
      </button>
      
      {isImageFile(file) ? (
        <img 
          src={file.data} 
          alt={file.name} 
          className="file-thumb-img"
          loading="lazy" // Performance optimization for many images
        />
      ) : (
        <div className="file-thumb-other">
          <span className="file-icon" role="img" aria-label="Document file">
            📄
          </span>
          <span className="file-name" title={file.name}>
            {file.name}
          </span>
        </div>
      )}
    </div>
  )
}

/**
 * File preview area component for displaying all selected files.
 * 
 * This component orchestrates the display of multiple files in a preview area
 * above the input field. It handles the layout, overflow, and provides a
 * clean interface for file management.
 * 
 * Features:
 * - Responsive grid layout for multiple files
 * - Scrollable area for many files
 * - Empty state handling (hidden when no files)
 * - File count management with optional limits
 * - Accessible file operations
 * 
 * Args:
 *     files: FileData[] - Array of files to display
 *     onRemoveFile: Function to handle file removal by index
 *     className?: string - Optional CSS class for customization
 *     maxDisplayFiles?: number - Maximum files to display (rest scrollable)
 * 
 * Returns:
 *     JSX.Element | null: File preview area or null if no files
 * 
 * TypeScript Learning Points:
 * - Array mapping with type safety
 * - Conditional rendering with early return
 * - Component composition with child components
 * - Props threading between parent and child components
 * - CSS class composition with template literals
 */
const FilePreviewArea: React.FC<FilePreviewAreaProps> = ({ 
  files, 
  onRemoveFile, 
  className = '',
  maxDisplayFiles = 20 
}) => {
  // Early return for empty state
  if (files.length === 0) return null
  
  // Limit displayed files for performance
  const displayFiles = files.slice(0, maxDisplayFiles)
  const hasMoreFiles = files.length > maxDisplayFiles
  
  return (
    <div className={`file-preview-area ${className}`.trim()}>
      {displayFiles.map((file, index) => (
        <FilePreviewItem
          key={`${file.name}-${index}`} // Unique key combining name and index
          file={file}
          index={index}
          onRemove={onRemoveFile}
          className="file-preview-item"
        />
      ))}
      
      {hasMoreFiles && (
        <div className="file-overflow-indicator">
          <span className="overflow-text">
            +{files.length - maxDisplayFiles} more files
          </span>
        </div>
      )}
    </div>
  )
}

export default FilePreviewArea

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **Component Composition Pattern**:
 *    ```typescript
 *    const FilePreviewArea: React.FC<FilePreviewAreaProps> = ({ files, onRemoveFile }) => {
 *      return (
 *        <div>
 *          {files.map((file, index) => (
 *            <FilePreviewItem file={file} index={index} onRemove={onRemoveFile} />
 *          ))}
 *        </div>
 *      )
 *    }
 *    ```
 *    Parent component orchestrates child components with props threading
 * 
 * 2. **Array Mapping with Type Safety**:
 *    ```typescript
 *    const displayFiles = files.slice(0, maxDisplayFiles)
 *    {displayFiles.map((file, index) => (
 *      <FilePreviewItem key={`${file.name}-${index}`} />
 *    ))}
 *    ```
 *    TypeScript ensures file object has expected properties
 * 
 * 3. **Conditional Rendering Patterns**:
 *    ```typescript
 *    if (files.length === 0) return null
 *    {isImageFile(file) ? <img /> : <div />}
 *    {hasMoreFiles && <div>overflow indicator</div>}
 *    ```
 *    Multiple conditional rendering techniques with type safety
 * 
 * 4. **Type Guard Usage**:
 *    ```typescript
 *    {isImageFile(file) ? (
 *      <img src={file.data} />
 *    ) : (
 *      <div className="file-thumb-other" />
 *    )}
 *    ```
 *    Type guards enable safe conditional rendering based on file type
 * 
 * 5. **Event Handler Props**:
 *    ```typescript
 *    interface FilePreviewItemProps {
 *      onRemove: (index: number) => void
 *    }
 *    const handleRemove = () => onRemove(index)
 *    ```
 *    Type-safe event handler passing between components
 * 
 * 6. **Template Literal Class Names**:
 *    ```typescript
 *    className={`file-thumb-box ${className}`.trim()}
 *    ```
 *    Dynamic class composition with cleanup
 * 
 * Component Design Benefits:
 * - **Single Responsibility**: FilePreviewItem handles one file, FilePreviewArea handles collection
 * - **Reusability**: Components can be used in other contexts
 * - **Type Safety**: Complete TypeScript coverage prevents runtime errors
 * - **Performance**: Lazy loading, slice limits, and proper key props
 * - **Accessibility**: ARIA labels and semantic HTML structure
 * - **User Experience**: Clear file management with visual feedback
 * 
 * Layout Strategy:
 * - CSS Grid/Flexbox for responsive file thumbnails
 * - Scrollable container for overflow handling
 * - Fixed aspect ratios for consistent appearance
 * - Hover effects for interactive elements
 * 
 * Performance Optimizations:
 * - Lazy loading for image thumbnails
 * - Slice-based display limits for large file collections
 * - Proper React keys for efficient re-rendering
 * - Conditional rendering prevents empty DOM elements
 * 
 * Accessibility Features:
 * - ARIA labels for screen readers
 * - Keyboard navigation support
 * - High contrast friendly styling
 * - Semantic HTML structure
 * - Title attributes for truncated text
 * 
 * Integration Pattern:
 * ```typescript
 * <FilePreviewArea
 *   files={files}
 *   onRemoveFile={removeFile}
 *   maxDisplayFiles={20}
 * />
 * ```
 * 
 * This pattern separates file display concerns from input logic,
 * making both components easier to test, modify, and understand.
 */