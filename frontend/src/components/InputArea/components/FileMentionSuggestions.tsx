import React from 'react'
import { FileMentionSuggestion } from '../types'

/**
 * File mention suggestions dropdown component.
 *
 * This component displays intelligent file suggestions when the user
 * types an '@' character, providing an intuitive way to discover and
 * select workspace files with visual feedback and keyboard navigation.
 *
 * Features:
 * - Real-time suggestion filtering based on partial input
 * - Relevance-based ranking with visual scoring indicators
 * - Hover and keyboard selection support
 * - File type icons and path display
 * - Rich file information with scores
 * - Smooth animations and modern UI design
 * - Accessibility support with proper ARIA attributes
 *
 * Args:
 *     suggestions: Array of ranked FileMentionSuggestion objects
 *     onSelectSuggestion: Callback when user selects a suggestion
 *     selectedIndex?: number - Currently highlighted suggestion index
 *     className?: string - Additional CSS classes
 *     maxDisplaySuggestions?: number - Maximum suggestions to display
 *     isLoading?: boolean - Show loading state during search
 *
 * Returns:
 *     JSX.Element: Styled suggestions dropdown with interactive elements
 *
 * TypeScript Learning Points:
 * - Component props with callback functions
 * - Array rendering with proper key props
 * - Conditional CSS class application
 * - Event handler typing for different interaction methods
 * - Props interface design with optional parameters
 */

export interface FileMentionSuggestionsProps {
  suggestions: FileMentionSuggestion[]
  onSelectSuggestion: (suggestion: FileMentionSuggestion) => void
  selectedIndex?: number
  className?: string
  maxDisplaySuggestions?: number
  isLoading?: boolean
}

const FileMentionSuggestions: React.FC<FileMentionSuggestionsProps> = ({
  suggestions,
  onSelectSuggestion,
  selectedIndex = 0,
  className = '',
  maxDisplaySuggestions = 10,
  isLoading = false
}) => {

  // Don't render if no suggestions and not loading
  if (suggestions.length === 0 && !isLoading) return null

  // Limit displayed suggestions
  const displaySuggestions = suggestions.slice(0, maxDisplaySuggestions)

  // Handle suggestion selection
  const handleSuggestionClick = (suggestion: FileMentionSuggestion) => {
    onSelectSuggestion(suggestion)
  }

  // Get relevance badge color based on score
  const getRelevanceBadgeColor = (score: number): string => {
    if (score >= 90) return 'high-relevance'
    if (score >= 70) return 'medium-relevance'
    return 'low-relevance'
  }

  // Get file type icon based on extension
  const getFileIcon = (filename: string): string => {
    const extension = filename.split('.').pop()?.toLowerCase()

    switch (extension) {
      case 'py': return '🐍'
      case 'ts':
      case 'tsx': return '📘'
      case 'js':
      case 'jsx': return '📜'
      case 'md': return '📝'
      case 'json': return '📋'
      case 'txt': return '📄'
      case 'css':
      case 'scss': return '🎨'
      case 'html': return '🌐'
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif':
      case 'svg': return '🖼️'
      default: return '📁'
    }
  }

  // Extract directory from path
  const getDirectory = (path: string): string => {
    const parts = path.split('/')
    if (parts.length <= 1) return ''
    return parts.slice(0, -1).join('/') + '/'
  }

  return (
    <div className={`file-mention-suggestions ${className}`.trim()}>
      <div className="suggestions-header">
        <span className="suggestions-title">Files</span>
        {isLoading ? (
          <span className="suggestions-loading">Searching...</span>
        ) : (
          <span className="suggestions-count">{displaySuggestions.length}</span>
        )}
      </div>

      <div className="suggestions-list">
        {isLoading && displaySuggestions.length === 0 ? (
          <div className="suggestion-loading-state">
            <span className="loading-spinner">⏳</span>
            <span className="loading-text">Searching files...</span>
          </div>
        ) : (
          displaySuggestions.map((suggestion, index) => {
            const directory = getDirectory(suggestion.file.path)

            return (
              <div
                key={suggestion.file.path}
                className={`suggestion-item ${index === selectedIndex ? 'selected' : ''}`.trim()}
                onClick={() => handleSuggestionClick(suggestion)}
                onMouseEnter={() => {
                  // Mouse hover could update selectedIndex in parent
                }}
                role="option"
                aria-selected={index === selectedIndex}
                tabIndex={-1}
              >
                {/* File icon and name */}
                <div className="suggestion-main">
                  <div className="suggestion-file">
                    <span className="file-icon">
                      {getFileIcon(suggestion.file.filename)}
                    </span>
                    <div className="file-info">
                      <div className="file-path-container">
                        {directory && (
                          <span className="file-directory">{directory}</span>
                        )}
                        <span className="file-name">{suggestion.file.filename}</span>
                      </div>
                      <div className="file-full-path">
                        {suggestion.file.path}
                      </div>
                    </div>
                    <span className={`relevance-badge ${getRelevanceBadgeColor(suggestion.relevanceScore)}`}>
                      {Math.round(suggestion.relevanceScore)}%
                    </span>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Footer with usage hint */}
      <div className="suggestions-footer">
        <span className="usage-hint">
          ↑↓ to navigate • ⏎ to select • esc to cancel
        </span>
      </div>
    </div>
  )
}

export default FileMentionSuggestions

/**
 * TypeScript Concepts Demonstrated:
 *
 * 1. **Component Props Interface Design**:
 *    ```typescript
 *    interface FileMentionSuggestionsProps {
 *      suggestions: FileMentionSuggestion[]
 *      onSelectSuggestion: (suggestion: FileMentionSuggestion) => void
 *      isLoading?: boolean
 *    }
 *    ```
 *    Clean props interface with callback functions and optional parameters
 *
 * 2. **Array Processing with Type Safety**:
 *    ```typescript
 *    const displaySuggestions = suggestions.slice(0, maxDisplaySuggestions)
 *    displaySuggestions.map((suggestion, index) => (
 *      <div key={suggestion.file.path}>
 *    ```
 *    Type-safe array operations with proper React key props
 *
 * 3. **Conditional Rendering Patterns**:
 *    ```typescript
 *    {isLoading ? <Spinner /> : <Results />}
 *    {directory && <span>{directory}</span>}
 *    ```
 *    Multiple conditional rendering strategies for different use cases
 *
 * 4. **Dynamic CSS Class Composition**:
 *    ```typescript
 *    className={`suggestion-item ${index === selectedIndex ? 'selected' : ''}`.trim()}
 *    ```
 *    Dynamic class application based on component state
 *
 * 5. **String Manipulation with Type Safety**:
 *    ```typescript
 *    const extension = filename.split('.').pop()?.toLowerCase()
 *    const directory = path.split('/').slice(0, -1).join('/')
 *    ```
 *    Safe string operations with optional chaining
 *
 * Component Architecture Benefits:
 * - **Focused Responsibility**: Only handles file suggestion display and selection
 * - **Rich User Experience**: Visual indicators, hover states, keyboard hints
 * - **Accessibility**: Proper ARIA attributes and semantic HTML
 * - **Performance**: Efficient rendering with proper React keys
 * - **Customizable**: Flexible props for different use cases
 * - **Type Safety**: Complete TypeScript coverage prevents errors
 *
 * Integration with InputArea:
 * ```typescript
 * const { suggestions, isMentionActive, selectSuggestion, isSearching } =
 *   useFileMentionDetection(message, cursorPosition)
 *
 * {isMentionActive && (
 *   <FileMentionSuggestions
 *     suggestions={suggestions}
 *     onSelectSuggestion={selectSuggestion}
 *     selectedIndex={selectedSuggestionIndex}
 *     isLoading={isSearching}
 *   />
 * )}
 * ```
 *
 * CSS Classes Used:
 * - .file-mention-suggestions: Main container
 * - .suggestions-header: Title and count display
 * - .suggestions-loading: Loading text
 * - .suggestions-list: Scrollable list container
 * - .suggestion-item: Individual suggestion row
 * - .suggestion-item.selected: Highlighted selection state
 * - .suggestion-file: File information container
 * - .file-icon: File type emoji
 * - .file-directory: Directory path (gray text)
 * - .file-name: Filename (bold)
 * - .file-full-path: Full relative path (small text)
 * - .relevance-badge: Score indicator
 * - .suggestions-footer: Usage instructions
 * - .suggestion-loading-state: Loading spinner state
 */
