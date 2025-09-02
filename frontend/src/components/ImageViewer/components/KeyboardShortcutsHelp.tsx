import React from 'react'

/**
 * Keyboard shortcuts help component for ImageViewer.
 * 
 * Displays helpful text about available keyboard shortcuts at the bottom
 * of the viewer. Provides users with quick reference for navigation.
 * 
 * Returns:
 *     JSX.Element: Help text with keyboard shortcuts
 * 
 * TypeScript Learning Points:
 * - Simple functional component with no props
 * - Static content component
 * - Accessibility with proper semantic HTML
 */
const KeyboardShortcutsHelp: React.FC = () => {
  return (
    <div className="keyboard-shortcuts">
      <div className="shortcuts-hint">
        Use arrow keys to navigate • Scroll or +/- to zoom • ESC to close
      </div>
    </div>
  )
}

export default KeyboardShortcutsHelp

/**
 * Enhanced version with dynamic content:
 * 
 * interface KeyboardShortcutsHelpProps {
 *   hasMultipleImages?: boolean
 *   showZoomHelp?: boolean
 *   customShortcuts?: Array<{ keys: string; description: string }>
 * }
 * 
 * const KeyboardShortcutsHelpAdvanced: React.FC<KeyboardShortcutsHelpProps> = ({
 *   hasMultipleImages = true,
 *   showZoomHelp = true,
 *   customShortcuts = []
 * }) => {
 *   const shortcuts = []
 *   
 *   if (hasMultipleImages) {
 *     shortcuts.push("Arrow keys to navigate")
 *   }
 *   
 *   if (showZoomHelp) {
 *     shortcuts.push("Scroll or +/- to zoom")
 *   }
 *   
 *   shortcuts.push("ESC to close")
 *   
 *   customShortcuts.forEach(shortcut => {
 *     shortcuts.push(`${shortcut.keys} ${shortcut.description}`)
 *   })
 * 
 *   return (
 *     <div className="keyboard-shortcuts">
 *       <div className="shortcuts-hint">
 *         {shortcuts.join(" • ")}
 *       </div>
 *     </div>
 *   )
 * }
 */

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Zero-Props Component:
 *    React.FC with no props interface needed
 * 
 * 2. Static Content:
 *    Component returning fixed JSX content
 * 
 * 3. Semantic HTML:
 *    Proper div structure for styling and accessibility
 * 
 * Benefits of This Component:
 * - Provides user guidance for keyboard shortcuts
 * - Consistent help text across image viewers
 * - Easy to modify shortcuts without changing main component
 * - Clean separation of help content
 * - Can be easily extended with dynamic content
 * 
 * CSS Classes Expected:
 * - .keyboard-shortcuts: Container positioning (usually bottom)
 * - .shortcuts-hint: Text styling with subtle appearance
 */