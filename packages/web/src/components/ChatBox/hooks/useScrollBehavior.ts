/**
 * Custom hook for managing ChatBox scroll behavior.
 * 
 * This hook demonstrates advanced React patterns with TypeScript:
 * - useRef with proper typing for DOM elements
 * - useEffect with dependency arrays
 * - Event handler typing
 * - Computed state management
 */

import { useRef, useEffect } from 'react'
import { Message } from '../../../types/chat'
import { UseScrollBehaviorReturn } from '../types'

/**
 * Manages automatic scrolling and click behavior for the chat container.
 * 
 * Features:
 * - Auto-scrolls to new messages when near bottom
 * - Maintains scroll position during streaming
 * - Handles click events for message deselection
 * 
 * Args:
 *     messages: Array of chat messages for scroll tracking
 *     setSelectedMessageId: Function to clear message selection
 * 
 * Returns:
 *     UseScrollBehaviorReturn: Object containing:
 *         - chatboxRef: Ref to attach to scrollable container
 *         - handleChatboxClick: Click handler for deselection
 * 
 * TypeScript Learning Points:
 * - useRef<HTMLDivElement>(null): Explicit typing for DOM refs
 * - React.MouseEvent: Proper event typing for handlers
 * - Dependency arrays must match hook inputs
 */
export const useScrollBehavior = (
  messages: Message[],
  setSelectedMessageId: (id: string | null) => void
): UseScrollBehaviorReturn => {
  // Ref typing: HTMLDivElement for div elements
  const chatboxRef = useRef<HTMLDivElement>(null)
  
  // Track previous message ID to detect new messages
  const prevLastMessageId = useRef<string | undefined>(messages[messages.length - 1]?.id)
  
  // Auto-scroll when messages change
  useEffect(() => {
    if (chatboxRef.current) {
      const chatBox = chatboxRef.current
      
      // Check if we should auto-scroll
      const shouldAutoScroll = 
        // User is near bottom (within 100px)
        chatBox.scrollHeight - chatBox.scrollTop <= chatBox.clientHeight + 100 ||
        // Or messages are streaming
        messages.some(msg => msg.streaming)
      
      if (shouldAutoScroll) {
        // Scroll to 80% visibility for better UX
        const scrollPosition = chatBox.scrollHeight - chatBox.clientHeight * 0.8
        chatBox.scrollTo({
          top: scrollPosition,
          behavior: 'smooth'
        })
      }
    }
  }, [messages]) // Dependency: re-run when messages change
  
  // Scroll to new messages
  useEffect(() => {
    const lastMessageId = messages[messages.length - 1]?.id
    
    // Only scroll if there's a new message
    if (lastMessageId && lastMessageId !== prevLastMessageId.current) {
      if (chatboxRef.current) {
        const chatBox = chatboxRef.current
        const scrollPosition = chatBox.scrollHeight - chatBox.clientHeight * 0.8
        chatBox.scrollTo({
          top: scrollPosition,
          behavior: 'smooth'
        })
      }
    }
    
    // Update tracked ID
    prevLastMessageId.current = lastMessageId
  }, [messages])
  
  // Handle click to deselect messages
  const handleChatboxClick = (e: React.MouseEvent) => {
    // Only deselect if clicking the container itself
    if (e.target === chatboxRef.current) {
      setSelectedMessageId(null)
    }
  }
  
  return {
    chatboxRef,
    handleChatboxClick
  }
}

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Generic Ref Types:
 *    useRef<HTMLDivElement>(null) - Specific DOM element typing
 * 
 * 2. Event Handler Types:
 *    (e: React.MouseEvent) => void - Proper React event typing
 * 
 * 3. Optional Chaining:
 *    messages[messages.length - 1]?.id - Safe property access
 * 
 * 4. Array Methods with Type Inference:
 *    messages.some(msg => msg.streaming) - TypeScript knows msg is Message
 * 
 * 5. Hook Return Types:
 *    Explicit return type ensures contract with consumers
 */