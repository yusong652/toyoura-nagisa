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

// Advanced thinking verbs (AI, DEM simulation, geotechnical engineering, and playful ones)
const THINKING_VERBS = [
  'Reasoning',      // AI
  'Analyzing',      // General
  'Computing',      // Numerical
  'Simulating',     // DEM
  'Synthesizing',   // AI
  'Calibrating',    // Engineering
  'Iterating',      // Numerical
  'Evaluating',     // Analysis
  'Optimizing',     // Optimization
  'Converging',     // Numerical
  'Processing',     // Data
  'Interpreting',   // Analysis
  'Formulating',    // Problem solving
  'Orchestrating',  // AI coordination
  'Consolidating',  // Geotechnical - soil consolidation
  'Saturating',     // Geotechnical - soil saturation
  'Compacting',     // Geotechnical - soil compaction
  'Liquefying',     // Geotechnical - soil liquefaction
  'Bouncing',       // Playful - particle collision
  'Siliconizing',   // Playful - Toyoura sand reference (silicon dioxide)
  'Pondering',      // Playful - cute thinking
  'Tinkering',      // Playful - experimental
  'Daydreaming',    // Playful - very cute
  'Materializing',  // Playful - making things real
  'Crystallizing',  // Playful - forming structure (sand crystals)
  'Percolating'     // Playful - sand/fluid dynamics + coffee brewing
]

const TodoStatusIndicator: React.FC<TodoStatusIndicatorProps> = ({ isLLMThinking }) => {
  const [currentTodo, setCurrentTodo] = useState<TodoItem | null>(null)
  const { currentSessionId } = useSession()
  const { pendingToolConfirmation } = useConnection()
  const [glowPosition, setGlowPosition] = useState(0)
  const [thinkingVerb] = useState(() =>
    THINKING_VERBS[Math.floor(Math.random() * THINKING_VERBS.length)]
  )

  // Random duration for speed variation (6-10 seconds)
  const [duration] = useState(() => 6000 + Math.random() * 4000)

  // Shimmer animation using requestAnimationFrame
  useEffect(() => {
    let animationFrameId: number
    let startTime: number | null = null

    const animate = (timestamp: number) => {
      if (!startTime) startTime = timestamp
      const elapsed = timestamp - startTime
      const progress = (elapsed % duration) / duration

      // Progress goes from 0 to 1, we map it to -1 to 2 (to cover full text width)
      setGlowPosition(progress * 3 - 1)

      animationFrameId = requestAnimationFrame(animate)
    }

    animationFrameId = requestAnimationFrame(animate)

    return () => {
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId)
      }
    }
  }, [duration])

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

  // Show todo status if available, otherwise show thinking verb
  const text = currentTodo ? currentTodo.activeForm : thinkingVerb

  // Calculate glow for each character
  const renderGlowText = () => {
    return text.split('').map((char, index) => {
      const charPosition = index / text.length
      const distance = Math.abs(charPosition - glowPosition)

      // Glow intensity: bright when distance is small, dim when far
      // Use smooth falloff over 0.15 range (about 2-3 characters)
      const glowIntensity = Math.max(0, 1 - distance / 0.15)

      // Enhanced brightness: base 0.6, peak 1.0 (40% boost when glowing)
      const opacity = 0.6 + glowIntensity * 0.4

      return (
        <span
          key={index}
          style={{
            opacity,
            transition: 'opacity 0.1s linear'
          }}
        >
          {char}
        </span>
      )
    })
  }

  return (
    <div className="todo-status-indicator">
      <div className="todo-spinner" />
      <span className="todo-label-shimmer">
        {renderGlowText()}
      </span>
    </div>
  )
}

export default TodoStatusIndicator
