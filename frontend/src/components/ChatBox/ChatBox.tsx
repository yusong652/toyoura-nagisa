/**
 * Refactored ChatBox component with modular architecture.
 * 
 * This component orchestrates the chat interface using smaller,
 * focused components and custom hooks for better maintainability
 * and TypeScript type safety.
 */

import React from 'react'
import { useChat } from '../../contexts/chat/ChatContext'
import { 
  useScrollBehavior, 
  useTitleManagement, 
  useMessageSelection 
} from './hooks'
import ChatBoxTitleBar from './components/ChatBoxTitleBar'
import MessageList from './components/MessageList'
import ChatBoxControls from './components/ChatBoxControls'
import ShadowOverlay from './components/ShadowOverlay'
import { LiveToolStateDisplay } from '../Tools'
import './ChatBox.css'

/**
 * Main ChatBox component with clean architecture.
 * 
 * Orchestrates:
 * - Title bar with refresh functionality
 * - Scrollable message list
 * - Control buttons
 * - Visual shadows for scroll indication
 * 
 * Architecture Benefits:
 * - Separation of concerns with custom hooks
 * - Modular components for each UI section
 * - Type-safe throughout with TypeScript
 * - Easy to test and maintain
 * 
 * TypeScript Learning Points:
 * - Custom hook composition
 * - Component composition pattern
 * - Props spreading vs explicit passing
 * - Ref forwarding to DOM elements
 */
interface ChatBoxProps {
  statusPanel?: React.ReactNode
}

const ChatBox: React.FC<ChatBoxProps> = ({ statusPanel }) => {
  // Get messages from context
  const { messages } = useChat()
  
  // Custom hooks for separated logic
  const { selectedMessageId, setSelectedMessageId } = useMessageSelection()
  const { chatboxRef, handleChatboxClick } = useScrollBehavior(messages, setSelectedMessageId)
  const { 
    currentSessionTitle, 
    isRefreshingTitle, 
    canRefreshTitle, 
    handleRefreshTitle,
    currentSessionId
  } = useTitleManagement(messages)
  
  return (
    <>
      {/* Title Bar Section */}
      <ChatBoxTitleBar
        currentSessionTitle={currentSessionTitle}
        currentSessionId={currentSessionId}
        isRefreshingTitle={isRefreshingTitle}
        canRefreshTitle={canRefreshTitle}
        onRefreshTitle={handleRefreshTitle}
      />
      
      {/* Main Chat Container */}
      <div className="chatbox-container">
        {/* Top Shadow for scroll indication */}
        <ShadowOverlay position="top" />
        
        {/* Scrollable Message Area */}
        <div 
          className="chatbox" 
          ref={chatboxRef}
          onClick={handleChatboxClick}
        >
          <MessageList
            messages={messages}
            selectedMessageId={selectedMessageId}
            onMessageSelect={setSelectedMessageId}
          />
          
          {/* Live Tool State Display - shows real-time tool usage */}
          <LiveToolStateDisplay />

          {/* Scroll anchor for maintaining position */}
          <div className="scroll-anchor" />
        </div>
        
        {/* Control Buttons */}
        <ChatBoxControls />
        
        {/* Bottom Shadow for scroll indication */}
        <ShadowOverlay position="bottom" />
        
        {/* Status panel via props composition */}
        {statusPanel}
      </div>
    </>
  )
}

export default ChatBox

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Custom Hook Composition:
 *    Multiple hooks working together to manage complex state
 * 
 * 2. Destructuring with Type Inference:
 *    const { messages } = useChat() - TypeScript knows the types
 * 
 * 3. Ref Forwarding:
 *    ref={chatboxRef} - Typed ref to HTMLDivElement
 * 
 * 4. Component Props:
 *    Each child component receives typed props
 * 
 * 5. Literal Types in Action:
 *    position="top" and position="bottom" - Type-safe literals
 * 
 * Benefits of This Architecture:
 * - Each component has a single responsibility
 * - Logic is extracted into testable hooks
 * - Type safety throughout the component tree
 * - Easy to add new features or modify existing ones
 * - Better performance with potential for memoization
 */