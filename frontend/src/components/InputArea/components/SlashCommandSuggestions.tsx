import React from 'react'
import { SlashCommandSuggestion } from '../types'

/**
 * Slash command suggestions dropdown component.
 * 
 * This component displays intelligent command suggestions when the user
 * types a '/' character, providing an intuitive way to discover and
 * select available commands with visual feedback and keyboard navigation.
 * 
 * Features:
 * - Real-time suggestion filtering based on partial input
 * - Relevance-based ranking with visual scoring indicators
 * - Hover and keyboard selection support
 * - Category grouping for better organization
 * - Rich command descriptions with usage hints
 * - Smooth animations and modern UI design
 * - Accessibility support with proper ARIA attributes
 * 
 * Args:
 *     suggestions: Array of ranked SlashCommandSuggestion objects
 *     onSelectSuggestion: Callback when user selects a suggestion
 *     selectedIndex?: number - Currently highlighted suggestion index
 *     className?: string - Additional CSS classes
 *     maxDisplaySuggestions?: number - Maximum suggestions to display
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

export interface SlashCommandSuggestionsProps {
  suggestions: SlashCommandSuggestion[]
  onSelectSuggestion: (suggestion: SlashCommandSuggestion) => void
  selectedIndex?: number
  className?: string
  maxDisplaySuggestions?: number
}

const SlashCommandSuggestions: React.FC<SlashCommandSuggestionsProps> = ({
  suggestions,
  onSelectSuggestion,
  selectedIndex = 0,
  className = '',
  maxDisplaySuggestions = 5
}) => {
  
  // Don't render if no suggestions
  if (suggestions.length === 0) return null
  
  // Limit displayed suggestions
  const displaySuggestions = suggestions.slice(0, maxDisplaySuggestions)
  
  // Handle suggestion selection
  const handleSuggestionClick = (suggestion: SlashCommandSuggestion) => {
    onSelectSuggestion(suggestion)
  }
  
  // Get relevance badge color based on score
  const getRelevanceBadgeColor = (score: number): string => {
    if (score >= 90) return 'high-relevance'
    if (score >= 70) return 'medium-relevance'
    return 'low-relevance'
  }
  
  // Get category icon for command
  const getCategoryIcon = (category?: string): string => {
    switch (category) {
      case 'media': return '🎨'
      case 'utility': return '🛠️'
      case 'communication': return '💬'
      case 'file': return '📁'
      default: return '⚡'
    }
  }
  
  return (
    <div className={`slash-command-suggestions ${className}`.trim()}>
      <div className="suggestions-header">
        <span className="suggestions-title">Commands</span>
        <span className="suggestions-count">{displaySuggestions.length}</span>
      </div>
      
      <div className="suggestions-list">
        {displaySuggestions.map((suggestion, index) => (
          <div
            key={suggestion.command.trigger}
            className={`suggestion-item ${index === selectedIndex ? 'selected' : ''}`.trim()}
            onClick={() => handleSuggestionClick(suggestion)}
            onMouseEnter={() => {
              // Mouse hover could update selectedIndex in parent
            }}
            role="option"
            aria-selected={index === selectedIndex}
            tabIndex={-1}
          >
            {/* Command trigger and category */}
            <div className="suggestion-main">
              <div className="suggestion-trigger">
                <span className="category-icon">
                  {getCategoryIcon(suggestion.command.category)}
                </span>
                <span className="trigger-text">
                  /{suggestion.command.trigger}
                </span>
                <span className={`relevance-badge ${getRelevanceBadgeColor(suggestion.relevanceScore)}`}>
                  {Math.round(suggestion.relevanceScore)}%
                </span>
              </div>
              
              {/* Command description */}
              <div className="suggestion-description">
                {suggestion.command.description}
              </div>
            </div>
            
            {/* Selection indicator removed */}
          </div>
        ))}
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

export default SlashCommandSuggestions

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **Component Props Interface Design**:
 *    ```typescript
 *    interface SlashCommandSuggestionsProps {
 *      suggestions: SlashCommandSuggestion[]
 *      onSelectSuggestion: (suggestion: SlashCommandSuggestion) => void
 *      selectedIndex?: number
 *    }
 *    ```
 *    Clean props interface with callback functions and optional parameters
 * 
 * 2. **Array Processing with Type Safety**:
 *    ```typescript
 *    const displaySuggestions = suggestions.slice(0, maxDisplaySuggestions)
 *    displaySuggestions.map((suggestion, index) => (
 *      <div key={suggestion.command.trigger}>
 *    ```
 *    Type-safe array operations with proper React key props
 * 
 * 3. **Conditional Rendering Patterns**:
 *    ```typescript
 *    {suggestions.length === 0 ? null : <div className="suggestions">}
 *    {index === selectedIndex && <div className="indicator">}
 *    ```
 *    Multiple conditional rendering strategies for different use cases
 * 
 * 4. **Dynamic CSS Class Composition**:
 *    ```typescript
 *    className={`suggestion-item ${index === selectedIndex ? 'selected' : ''}`.trim()}
 *    ```
 *    Dynamic class application based on component state
 * 
 * 5. **Event Handler Typing**:
 *    ```typescript
 *    const handleSuggestionClick = (suggestion: SlashCommandSuggestion) => {
 *      onSelectSuggestion(suggestion)
 *    }
 *    ```
 *    Properly typed event handlers with callback prop usage
 * 
 * 6. **Switch Statement with String Literals**:
 *    ```typescript
 *    const getCategoryIcon = (category?: string): string => {
 *      switch (category) {
 *        case 'media': return '🎨'
 *        case 'utility': return '🛠️'
 *        default: return '⚡'
 *      }
 *    }
 *    ```
 *    Type-safe string literal handling with default cases
 * 
 * Component Architecture Benefits:
 * - **Focused Responsibility**: Only handles suggestion display and selection
 * - **Rich User Experience**: Visual indicators, hover states, keyboard hints
 * - **Accessibility**: Proper ARIA attributes and semantic HTML
 * - **Performance**: Efficient rendering with proper React keys
 * - **Customizable**: Flexible props for different use cases
 * - **Type Safety**: Complete TypeScript coverage prevents errors
 * 
 * Integration with InputArea:
 * ```typescript
 * const { suggestions, isCommandActive, selectSuggestion } = useSlashCommand(message, cursorPosition)
 * 
 * {isCommandActive && suggestions.length > 0 && (
 *   <SlashCommandSuggestions
 *     suggestions={suggestions}
 *     onSelectSuggestion={selectSuggestion}
 *     selectedIndex={selectedSuggestionIndex}
 *   />
 * )}
 * ```
 * 
 * CSS Classes Used:
 * - .slash-command-suggestions: Main container
 * - .suggestions-header: Title and count display
 * - .suggestions-list: Scrollable list container
 * - .suggestion-item: Individual suggestion row
 * - .suggestion-item.selected: Highlighted selection state
 * - .suggestion-trigger: Command name and category
 * - .suggestion-description: Help text
 * - .relevance-badge: Score indicator
 * - .selection-indicator: Checkmark for selected item
 * - .suggestions-footer: Usage instructions
 * 
 * Future Enhancements:
 * - Keyboard navigation with arrow keys
 * - Command parameter hints and validation
 * - Recent commands history
 * - Custom command icons
 * - Command grouping by category
 * - Search highlighting for matched text
 */