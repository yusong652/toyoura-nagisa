/**
 * Custom hook for managing message selection state.
 * 
 * Simple state management hook demonstrating TypeScript's union types
 * and state setter function typing.
 */

import { useState } from 'react'
import { UseMessageSelectionReturn } from '../types'

/**
 * Manages selected message state for the ChatBox.
 * 
 * This hook provides a simple abstraction for message selection,
 * demonstrating how even simple state can benefit from proper typing
 * and extraction into reusable hooks.
 * 
 * Returns:
 *     UseMessageSelectionReturn: Object containing:
 *         - selectedMessageId: Current selection (string | null)
 *         - setSelectedMessageId: Selection setter function
 * 
 * TypeScript Learning Points:
 * - Union types: string | null for optional values
 * - State setter typing: React.Dispatch<React.SetStateAction<T>>
 * - Explicit vs inferred types in useState
 */
export const useMessageSelection = (): UseMessageSelectionReturn => {
  // Explicit type annotation for clarity
  // Could also be: useState(null) with type inference
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)
  
  return {
    selectedMessageId,
    setSelectedMessageId
  }
}

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Union Types:
 *    string | null - Value can be either type
 * 
 * 2. Generic State:
 *    useState<string | null> - Explicit type parameter
 * 
 * 3. Function Types:
 *    setSelectedMessageId has type: (id: string | null) => void
 * 
 * 4. Simple Hook Pattern:
 *    Even simple hooks benefit from type safety
 * 
 * Why extract this simple state?
 * - Reusability across components
 * - Consistent typing
 * - Future enhancement possibility
 * - Separation of concerns
 */