/**
 * SidebarHeader component for ChatHistorySidebar.
 * 
 * Displays the sidebar title and close button, providing
 * clear visual hierarchy and intuitive close interaction.
 */

import React from 'react'
import { SidebarHeaderProps } from '../types'
import './SidebarHeader.css'

/**
 * Header component for the chat history sidebar.
 * 
 * This component demonstrates:
 * - Simple functional component with typed props
 * - SVG icon usage for close button
 * - CSS module organization for component styles
 * 
 * @param isOpen - Whether sidebar is currently open (unused but reserved)
 * @param onClose - Callback to close the sidebar
 */
const SidebarHeader: React.FC<SidebarHeaderProps> = ({ isOpen, onClose }) => {
  return (
    <div className="chat-history-header">
      <div className="chat-history-title">Chat History</div>
      <button 
        className="chat-history-close"
        onClick={onClose}
        aria-label="Close Chat History"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M2 2L12 12M2 12L12 2" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
    </div>
  )
}

export default SidebarHeader