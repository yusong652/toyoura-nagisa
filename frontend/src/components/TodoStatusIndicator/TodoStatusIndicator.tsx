/**
 * TodoStatusIndicator - Displays current in-progress todo status.
 *
 * Replaces the thinking indicator with actual task status from the backend.
 * Shows what the AI agent is currently working on in real-time.
 *
 * Features:
 * - Real-time todo status updates via WebSocket
 * - Smooth animations for status changes
 * - Fixed position at bottom left of chat
 * - Fallback to thinking indicator when no todo
 */

import React, { useState, useEffect } from 'react'
import { useSession } from '../../contexts/session/SessionContext'
import { useConnection } from '../../contexts/connection/ConnectionContext'
import './TodoStatusIndicator.css'

interface TodoItem {
  todo_id: string
  content: string
  activeForm: string
  status: 'pending' | 'in_progress' | 'completed'
  session_id: string
  created_at: number
  updated_at: number
  metadata?: Record<string, any>
}

interface TodoStatusIndicatorProps {
  isLLMThinking: boolean  // Fallback to thinking indicator when no todo
}

const TodoStatusIndicator: React.FC<TodoStatusIndicatorProps> = ({ isLLMThinking }) => {
  const [currentTodo, setCurrentTodo] = useState<TodoItem | null>(null)
  const { currentSessionId } = useSession()
  const { pendingToolConfirmation } = useConnection()

  // Generate random shimmer delay for natural animation variation (0-2 seconds)
  const [shimmerDelay] = useState(() => Math.random() * 2)

  // Fetch current todo on mount and session change
  useEffect(() => {
    const fetchCurrentTodo = async () => {
      if (!currentSessionId) {
        return
      }

      try {
        const response = await fetch(
          `http://localhost:8000/api/todos/current?session_id=${currentSessionId}`,
          {
            cache: 'no-cache',
            headers: {
              'Cache-Control': 'no-cache'
            }
          }
        )
        const data = await response.json()

        if (data.success && data.todo) {
          setCurrentTodo(data.todo)
        } else {
          setCurrentTodo(null)
        }
      } catch (error) {
        console.error('Failed to fetch current todo:', error)
        setCurrentTodo(null)
      }
    }

    fetchCurrentTodo()
  }, [currentSessionId])

  // Listen for todo update events from WebSocket
  useEffect(() => {
    const handleTodoUpdate = (event: Event) => {
      const customEvent = event as CustomEvent<{ todo: TodoItem | null }>
      setCurrentTodo(customEvent.detail.todo)
    }

    window.addEventListener('todoUpdate', handleTodoUpdate)

    return () => {
      window.removeEventListener('todoUpdate', handleTodoUpdate)
    }
  }, [])

  // Only show when LLM is actively working (thinking or waiting for confirmation)
  // Don't show idle todos - indicator's purpose is to show LLM is working
  if (!isLLMThinking && !pendingToolConfirmation) {
    return null
  }

  // Show todo status if available, otherwise show thinking indicator
  return (
    <div className="todo-status-indicator">
      <div className="todo-spinner" />
      <span
        className="todo-label"
        style={{ '--shimmer-delay': shimmerDelay } as React.CSSProperties}
      >
        {currentTodo ? currentTodo.activeForm : 'thinking'}
      </span>
    </div>
  )
}

export default TodoStatusIndicator
