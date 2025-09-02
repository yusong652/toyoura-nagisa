/**
 * Shadow overlay component for visual depth effects.
 * 
 * Creates gradient shadows at the top/bottom of scrollable areas
 * to indicate more content is available.
 */

import React from 'react'
import { ShadowOverlayProps } from '../types'

/**
 * Renders a shadow overlay for scroll indication.
 * 
 * This component adds visual depth to scrollable containers,
 * showing users that more content exists above or below.
 * 
 * Args:
 *     position: 'top' | 'bottom' - Literal type for shadow position
 * 
 * TypeScript Learning Points:
 * - Literal type props ('top' | 'bottom')
 * - Template literals for class names
 * - Pure presentational components
 */
const ShadowOverlay: React.FC<ShadowOverlayProps> = ({ position }) => {
  return (
    <div className={`chatbox-${position}-shadow`} />
  )
}

export default ShadowOverlay

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Literal Types:
 *    position: 'top' | 'bottom' - Only these exact strings allowed
 * 
 * 2. Template Literals in JSX:
 *    `chatbox-${position}-shadow` - Dynamic class generation
 * 
 * 3. Self-Closing Components:
 *    <div /> - No children needed
 * 
 * Usage Example:
 *    <ShadowOverlay position="top" />    // ✅ Valid
 *    <ShadowOverlay position="left" />   // ❌ TypeScript error
 * 
 * Why separate this component?
 * - Reusable for both top and bottom shadows
 * - Type-safe position prop
 * - Single responsibility
 * - Easy to test and style
 */