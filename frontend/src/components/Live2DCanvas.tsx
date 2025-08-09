import React, { useEffect, useRef } from 'react'
import './Live2DCanvas.css'
import { initializeLive2D, enableLive2DDrag } from '../utils/live2d'

const Live2DCanvas: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const loadLive2D = async () => {
      try {
        if (canvasRef.current) {
          console.log('Initializing Live2D model...')
          await initializeLive2D(canvasRef.current)
          // 启用拖动功能
          enableLive2DDrag(canvasRef.current)
        }
      } catch (error) {
        console.error('Failed to load Live2D model:', error)
      }
    }

    // 等待一小段时间确保DOM和脚本都已加载
    setTimeout(() => {
      loadLive2D()
    }, 500)

    return () => {
      // 清理函数
      if (canvasRef.current) {
        canvasRef.current.removeEventListener('mousedown', () => {})
        document.removeEventListener('mousemove', () => {})
        document.removeEventListener('mouseup', () => {})
      }
    }
  }, [])

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