/**
 * Live2D Toggle Component
 * 
 * Live2D display toggle using BaseToggle.
 */

import React, { useCallback } from 'react'
import { useLive2D } from '../../../contexts/live2d/Live2DContext'
import { BaseToggle } from '../base/BaseToggle'
import type { Live2DToggleProps } from '../types'

export const Live2DToggle: React.FC<Live2DToggleProps> = ({
  initialDisplay,
  onDisplayChange,
  className = ''
}) => {
  const { isLive2DEnabled, toggleLive2D } = useLive2D()

  const handleToggle = useCallback((checked: boolean) => {
    toggleLive2D(checked)
    onDisplayChange?.(checked)
  }, [toggleLive2D, onDisplayChange])

  return (
    <BaseToggle
      checked={isLive2DEnabled}
      onChange={handleToggle}
      className={className}
      ariaLabel="Toggle Live2D character display"
      data-testid="live2d-toggle"
    />
  )
}