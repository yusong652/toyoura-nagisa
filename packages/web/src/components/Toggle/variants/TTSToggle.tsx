/**
 * TTS Toggle Component
 * 
 * Text-to-speech toggle using BaseToggle with error handling.
 */

import React, { useCallback } from 'react'
import { useTtsEnable } from '../../../contexts/audio/TtsEnableContext'
import { useErrorDisplay } from '../../../hooks/useErrorDisplay'
import { BaseToggle } from '../base/BaseToggle'
import UnifiedErrorDisplay from '../../UnifiedErrorDisplay'
import type { TTSToggleProps } from '../types'

export const TTSToggle: React.FC<TTSToggleProps> = ({
  initialEnabled,
  onTTSChange,
  className = ''
}) => {
  const { ttsEnabled, updateTTSEnabled } = useTtsEnable()
  const { error, showTemporaryError, clearError } = useErrorDisplay()

  const handleToggle = useCallback(async (checked: boolean) => {
    try {
      await updateTTSEnabled(checked)
      onTTSChange?.(checked)
    } catch (error) {
      console.error('Failed to toggle TTS status:', error)
      showTemporaryError('Failed to toggle text-to-speech. Please try again.', 3000)
    }
  }, [updateTTSEnabled, onTTSChange, showTemporaryError])

  return (
    <>
      <BaseToggle
        checked={ttsEnabled}
        onChange={handleToggle}
        className={className}
        ariaLabel="Toggle text-to-speech"
        data-testid="tts-toggle"
      />
      <UnifiedErrorDisplay
        error={error}
        onClose={clearError}
      />
    </>
  )
}