import React from 'react'
import { ImageControlsProps } from '../types'

/**
 * Control buttons component for ImageViewer.
 * 
 * Provides zoom in, zoom out, and zoom reset controls with
 * proper disabled states and accessibility labels. Supports
 * auto-hide functionality for cleaner viewing experience.
 * 
 * Args:
 *     zoom: Current zoom level for display
 *     canZoomIn: Whether zoom in is possible
 *     canZoomOut: Whether zoom out is possible  
 *     onZoomIn: Handler for zoom in button
 *     onZoomOut: Handler for zoom out button
 *     onZoomReset: Handler for zoom reset button
 *     visible: Whether controls should be visible (auto-hide support)
 *     className: Additional CSS classes for styling
 * 
 * Returns:
 *     JSX.Element | null: Control buttons with zoom indicator or null when hidden
 * 
 * TypeScript Learning Points:
 * - Props with boolean state for button enabling
 * - Conditional rendering based on visibility
 * - Mathematical rounding for display
 * - SVG icon components with consistent styling
 * - CSS class composition with visibility control
 */
const ImageControls: React.FC<ImageControlsProps> = ({
  zoom,
  canZoomIn,
  canZoomOut,
  onZoomIn,
  onZoomOut,
  onZoomReset,
  className = ''
}) => {
  return (
    <div className={`image-controls ${className}`.trim()}>
      {/* Zoom Out Button */}
      <button 
        className="control-btn" 
        onClick={onZoomOut}
        disabled={!canZoomOut}
        aria-label="Zoom out"
        type="button"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
          <line x1="8" y1="12" x2="16" y2="12" stroke="currentColor" strokeWidth="2"/>
        </svg>
      </button>
      
      {/* Zoom Level Indicator */}
      <span className="zoom-indicator">{Math.round(zoom * 100)}%</span>
      
      {/* Zoom In Button */}
      <button 
        className="control-btn" 
        onClick={onZoomIn}
        disabled={!canZoomIn}
        aria-label="Zoom in"
        type="button"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
          <line x1="8" y1="12" x2="16" y2="12" stroke="currentColor" strokeWidth="2"/>
          <line x1="12" y1="8" x2="12" y2="16" stroke="currentColor" strokeWidth="2"/>
        </svg>
      </button>
      
      {/* Reset Zoom Button */}
      <button 
        className="control-btn" 
        onClick={onZoomReset}
        aria-label="Reset zoom to 100%"
        title="Reset zoom to fit"
        type="button"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 2L12 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          <path d="M12 18L12 22" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          <path d="M22 12L18 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          <path d="M6 12L2 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="2" fill="none"/>
        </svg>
      </button>
    </div>
  )
}

export default ImageControls

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Boolean Props for State:
 *    canZoomIn/canZoomOut control button availability
 * 
 * 2. Mathematical Operations:
 *    Math.round(zoom * 100) for percentage display
 * 
 * 3. Conditional Attributes:
 *    disabled={!canZoom} for dynamic button states
 * 
 * 4. Accessibility Features:
 *    aria-label, title, and type attributes
 * 
 * 5. SVG Icon Consistency:
 *    Standardized icon sizes and stroke properties
 * 
 * Benefits of This Component:
 * - Consistent control UI across image viewers
 * - Proper accessibility with screen reader support
 * - Visual feedback for disabled states
 * - Clear zoom level indication
 * - Reusable control pattern
 * 
 * CSS Classes Expected:
 * - .image-controls: Container with button layout
 * - .control-btn: Individual button styling
 * - .zoom-indicator: Text display for zoom percentage
 */