import React, { useEffect, useRef } from 'react'
import './Live2DCanvas.css'
import { initializeLive2D, enableLive2DDrag } from '../utils/live2d'
import { useLive2D } from '../contexts/live2d/Live2DContext'

const Live2DCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const { isLive2DEnabled } = useLive2D()

  useEffect(() => {
    if (!isLive2DEnabled) return

    const loadLive2D = async () => {
      try {
        if (canvasRef.current) {
          console.log('Initializing Live2D model...')
          await initializeLive2D(canvasRef.current)
          // Enable drag functionality
          enableLive2DDrag(canvasRef.current)
          
          // Add interactive class to enable pointer events when needed
          // This allows dragging while preventing accidental blocking
          canvasRef.current.classList.add('interactive')
        }
      } catch (error) {
        console.error('Failed to load Live2D model:', error)
      }
    }

    // Wait a moment to ensure DOM and scripts are loaded
    const timer = setTimeout(() => {
      loadLive2D()
    }, 500)

    return () => {
      clearTimeout(timer)
      // Cleanup function
      if (canvasRef.current) {
        canvasRef.current.removeEventListener('mousedown', () => {})
        document.removeEventListener('mousemove', () => {})
        document.removeEventListener('mouseup', () => {})
      }
    }
  }, [isLive2DEnabled])

  // Only render canvas when Live2D is enabled
  if (!isLive2DEnabled) {
    return null
  }

  return <canvas id="live2d-canvas" ref={canvasRef}></canvas>
}

export default Live2DCanvas

// 为了TypeScript支持，声明全局对象
declare global {
  interface Window {
    Live2DCubismCore: any
    live2d: any
  }
} 