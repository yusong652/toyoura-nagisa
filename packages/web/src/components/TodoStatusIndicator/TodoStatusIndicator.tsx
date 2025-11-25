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
import { useAgent } from '../../contexts/agent/AgentContext'
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
  const { currentProfile } = useAgent()
  const [glowPosition, setGlowPosition] = useState(0)
  const [thinkingVerb, setThinkingVerb] = useState(() =>
    THINKING_VERBS[Math.floor(Math.random() * THINKING_VERBS.length)]
  )

  // Random duration for speed variation (2-10 seconds)
  const [duration] = useState(() => 2000 + Math.random() * 8000)

  // Particle collision animation state
  const canvasRef = React.useRef<HTMLCanvasElement>(null)

  // Determine if indicator should be visible
  // Only show when LLM is actively working (thinking or waiting for confirmation)
  const shouldShow = isLLMThinking || pendingToolConfirmation

  // Update thinking verb when LLM starts thinking (new conversation turn)
  useEffect(() => {
    if (isLLMThinking) {
      setThinkingVerb(THINKING_VERBS[Math.floor(Math.random() * THINKING_VERBS.length)])
    }
  }, [isLLMThinking])

  // Nagisa avatar animation (blinking eyes + moving ears + breathing)
  // Note: This useEffect runs after component mounts AND whenever shouldShow changes
  // This ensures canvas animation starts when component becomes visible
  useEffect(() => {
    if (!shouldShow) return // Don't start animation if component is hidden

    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d', {
      alpha: true,
      desynchronized: false,
      willReadFrequently: false
    })
    if (!ctx) return

    // Disable image smoothing for pixel-perfect rendering
    ctx.imageSmoothingEnabled = false

    // Canvas size (match avatar resolution)
    const width = 32
    const height = 32
    canvas.width = width
    canvas.height = height

    const center = width / 2

    // Pre-compute circle pixels to avoid expensive sqrt calculations every frame
    // This optimization reduces 1024 iterations + sqrt calls to ~254 pixel lookups
    const circlePixels: Array<{x: number, y: number}> = []
    for (let i = 0; i < height; i++) {
      for (let j = 0; j < width; j++) {
        const dist = Math.sqrt((i - center) ** 2 + (j - center) ** 2)
        if (dist < 9) {
          circlePixels.push({x: j, y: i})
        }
      }
    }

    // Animation state
    let frameCount = 0
    let isBlinking = false
    let blinkFrame = 0
    // Random interval: 2-6 seconds at 30fps = 60-180 frames
    let nextBlinkTime = Math.random() * 120 + 60

    // Bouncing state
    let isBouncing = false
    let bounceFrame = 0
    // Random interval: 1-16 seconds at 30fps = 30-480 frames
    let nextBounceTime = Math.random() * 450 + 30

    // Frame rate control (30fps instead of 60fps)
    const targetFPS = 30
    const frameInterval = 1000 / targetFPS
    let lastFrameTime = performance.now()

    let animationFrameId: number

    const drawPixel = (x: number, y: number, color: string, scaleX: number = 1, scaleY: number = 1) => {
      ctx.fillStyle = color
      // Round to nearest pixel for cleaner rendering
      const px = Math.round(x)
      const py = Math.round(y)

      // When scaling, draw slightly larger rectangles to avoid gaps
      // Use ceil to ensure coverage when stretched
      const w = Math.max(1, Math.ceil(Math.abs(scaleX)))
      const h = Math.max(1, Math.ceil(Math.abs(scaleY)))

      ctx.fillRect(px, py, w, h)
    }

    const drawNagisa = (earOffset: number, eyeState: 'open' | 'closed', bounceY: number, squashStretch: { scaleX: number, scaleY: number }) => {
      ctx.clearRect(0, 0, width, height)

      // For pixel-perfect rendering, we'll apply transformations manually to coordinates
      // instead of using ctx.scale which causes anti-aliasing
      const applyTransform = (x: number, y: number): { x: number, y: number } => {
        // Apply squash/stretch around bottom center anchor point
        const bottomY = center + 9
        const dx = x - center
        const dy = y - bottomY

        const transformedX = center + dx * squashStretch.scaleX
        const transformedY = bottomY + dy * squashStretch.scaleY

        // Apply bounce offset AFTER squash/stretch
        // Clamp to ensure pixels stay within canvas bounds [0, height-1]
        const finalY = Math.max(0, Math.min(height - 1, transformedY + bounceY))

        return {
          x: transformedX,
          y: finalY
        }
      }

      const pink = '#FFB6C1'
      const white = '#FFFFFF'

      const earOffsetY = Math.round(earOffset)

      // Particle cluster ears (pixel style)
      // Left ear - main particle cluster (3x3 pixels)
      for (let i = 0; i < 3; i++) {
        for (let j = 0; j < 3; j++) {
          const pos = applyTransform(center - 7 + j, 6 + earOffsetY + i)
          drawPixel(pos.x, pos.y, pink, squashStretch.scaleX, squashStretch.scaleY)
        }
      }
      // Left ear - satellite particles
      let pos = applyTransform(center - 8, 7 + earOffsetY)
      drawPixel(pos.x, pos.y, pink, squashStretch.scaleX, squashStretch.scaleY)
      pos = applyTransform(center - 4, 7 + earOffsetY)
      drawPixel(pos.x, pos.y, pink, squashStretch.scaleX, squashStretch.scaleY)

      // Right ear - main particle cluster (3x3 pixels)
      for (let i = 0; i < 3; i++) {
        for (let j = 0; j < 3; j++) {
          const pos = applyTransform(center + 5 + j, 6 + earOffsetY + i)
          drawPixel(pos.x, pos.y, pink, squashStretch.scaleX, squashStretch.scaleY)
        }
      }
      // Right ear - satellite particles
      pos = applyTransform(center + 4, 7 + earOffsetY)
      drawPixel(pos.x, pos.y, pink, squashStretch.scaleX, squashStretch.scaleY)
      pos = applyTransform(center + 8, 7 + earOffsetY)
      drawPixel(pos.x, pos.y, pink, squashStretch.scaleX, squashStretch.scaleY)

      // Main ball body (using pre-computed circle pixels)
      // Performance: ~254 iterations instead of 1024, no sqrt calculations
      for (const pixel of circlePixels) {
        const pos = applyTransform(pixel.x, pixel.y)
        drawPixel(pos.x, pos.y, pink, squashStretch.scaleX, squashStretch.scaleY)
      }

      // Eyes
      if (eyeState === 'open') {
        // Left eye - open (◕) - 3 pixels vertical
        pos = applyTransform(center - 3, center - 3)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
        pos = applyTransform(center - 3, center - 2)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
        pos = applyTransform(center - 3, center - 1)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
        pos = applyTransform(center - 3, center - 4)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)

        // Right eye - open (◕)
        pos = applyTransform(center + 3, center - 3)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
        pos = applyTransform(center + 3, center - 2)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
        pos = applyTransform(center + 3, center - 1)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
        pos = applyTransform(center + 3, center - 4)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
      } else {
        // Both eyes closed (-) - horizontal lines
        pos = applyTransform(center - 4, center - 2)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
        pos = applyTransform(center - 3, center - 2)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
        pos = applyTransform(center - 2, center - 2)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)

        pos = applyTransform(center + 2, center - 2)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
        pos = applyTransform(center + 3, center - 2)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
        pos = applyTransform(center + 4, center - 2)
        drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
      }

      // Mouth (ω)
      pos = applyTransform(center - 1, center + 1)
      drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
      pos = applyTransform(center, center + 1)
      drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
      pos = applyTransform(center + 1, center + 1)
      drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
      pos = applyTransform(center, center + 2)
      drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)

      // Blush (2 pixels each side)
      pos = applyTransform(center - 7, center - 1)
      drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
      pos = applyTransform(center - 7, center)
      drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
      pos = applyTransform(center + 7, center - 1)
      drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
      pos = applyTransform(center + 7, center)
      drawPixel(pos.x, pos.y, white, squashStretch.scaleX, squashStretch.scaleY)
    }

    const animate = (currentTime: number) => {
      // Frame rate limiting (30fps)
      const elapsed = currentTime - lastFrameTime
      if (elapsed < frameInterval) {
        animationFrameId = requestAnimationFrame(animate)
        return
      }
      lastFrameTime = currentTime - (elapsed % frameInterval)

      frameCount++

      // Ear movement (gentle up-down when not bouncing)
      const earOffset = isBouncing ? 0 : Math.sin(frameCount * 0.05) * 0.5

      // Blinking logic
      let eyeState: 'open' | 'closed' = 'open'

      if (frameCount >= nextBlinkTime && !isBlinking) {
        isBlinking = true
        blinkFrame = 0
      }

      if (isBlinking) {
        blinkFrame++
        // Blink lasts 8 frames (closed for 4 frames)
        if (blinkFrame >= 2 && blinkFrame <= 5) {
          eyeState = 'closed'
        }
        if (blinkFrame >= 8) {
          isBlinking = false
          // Random interval: 2-6 seconds at 30fps = 60-180 frames
          nextBlinkTime = frameCount + Math.random() * 120 + 60
        }
      }

      // Bouncing logic (random bounces with squash & stretch)
      let bounceY = 0
      let squashStretch = { scaleX: 1.0, scaleY: 1.0 }

      if (frameCount >= nextBounceTime && !isBouncing) {
        isBouncing = true
        bounceFrame = 0
      }

      if (isBouncing) {
        bounceFrame++
        const bounceDuration = 30 // Total bounce duration in frames (1 second at 30fps)

        if (bounceFrame <= bounceDuration) {
          // Bounce phases:
          // 0-20%: Squash down (anticipation/windup)
          // 20-70%: Jump up (parabolic arc)
          // 70-100%: Land and settle
          const t = bounceFrame / bounceDuration

          if (t < 0.2) {
            // Phase 1: Squash down for anticipation (0-20%)
            const windupProgress = t / 0.2 // 0 to 1
            const windupAmount = Math.sin(windupProgress * Math.PI / 2) // Ease in

            // Squash down (wider and shorter)
            squashStretch.scaleX = 1.0 + windupAmount * 0.2
            squashStretch.scaleY = 1.0 - windupAmount * 0.2
            // bounceY stays 0 - bottom anchor handles this

          } else if (t < 0.7) {
            // Phase 2: Jump up (20-70%)
            const jumpProgress = (t - 0.2) / 0.5 // 0 to 1
            const maxHeight = 8

            // Parabolic trajectory: positive Y = upward (after transform order fix)
            bounceY = maxHeight * 4 * jumpProgress * (jumpProgress - 1)

            // Stretch at peak, normal at takeoff/landing
            if (jumpProgress < 0.3) {
              // Takeoff: slight stretch
              const stretchAmount = jumpProgress / 0.3
              squashStretch.scaleX = 1.0 - stretchAmount * 0.1
              squashStretch.scaleY = 1.0 + stretchAmount * 0.1
            } else if (jumpProgress > 0.7) {
              // Prepare for landing: slight squash
              const landingPrep = (jumpProgress - 0.7) / 0.3
              squashStretch.scaleX = 1.0 + landingPrep * 0.15
              squashStretch.scaleY = 1.0 - landingPrep * 0.15
            } else {
              // Peak: maximum stretch
              squashStretch.scaleX = 0.9
              squashStretch.scaleY = 1.1
            }

          } else {
            // Phase 3: Land and settle (70-100%)
            const settleProgress = (t - 0.7) / 0.3 // 0 to 1

            // Squash on landing, then bounce back to normal
            const settleAmount = Math.cos(settleProgress * Math.PI / 2) // Ease out

            squashStretch.scaleX = 1.0 + settleAmount * 0.12
            squashStretch.scaleY = 1.0 - settleAmount * 0.12
            // bounceY stays 0 - bottom anchor handles this
          }
        } else {
          isBouncing = false
          // Random interval: 1-16 seconds at 30fps = 30-480 frames
          nextBounceTime = frameCount + Math.random() * 450 + 30
        }
      }

      drawNagisa(earOffset, eyeState, bounceY, squashStretch)

      animationFrameId = requestAnimationFrame(animate)
    }

    animationFrameId = requestAnimationFrame(animate)

    return () => {
      if (animationFrameId) {
        cancelAnimationFrame(animationFrameId)
      }
    }
  }, [shouldShow])

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

  // Fetch current todo on mount and profile change
  useEffect(() => {
    const fetchCurrentTodo = async () => {
      try {
        // agent_profile is required, session_id is optional (for PFC workspace sync)
        const params = new URLSearchParams({ agent_profile: currentProfile })
        if (currentSessionId) {
          params.append('session_id', currentSessionId)
        }

        const response = await fetch(
          `http://localhost:8000/api/todos/current?${params}`,
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
  }, [currentSessionId, currentProfile])

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

  if (!shouldShow) {
    return null
  }

  return (
    <div className="todo-status-indicator">
      <canvas
        ref={canvasRef}
        className="nagisa-avatar"
        style={{ width: '24px', height: '24px' }}
      />
      <span className="todo-label-shimmer">
        {renderGlowText()}
      </span>
    </div>
  )
}

export default TodoStatusIndicator
