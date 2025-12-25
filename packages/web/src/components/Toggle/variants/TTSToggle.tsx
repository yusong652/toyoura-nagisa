/**
 * TTS Toggle Component
 *
 * Text-to-speech toggle using BaseToggle.
 * TTS state is managed purely in React Context and sent with each chat message.
 */

import React, { useCallback } from 'react'
import { useTtsEnable } from '../../../contexts/audio/TtsEnableContext'
import { BaseToggle } from '../base/BaseToggle'
import type { TTSToggleProps } from '../types'

export const TTSToggle: React.FC<TTSToggleProps> = ({
  initialEnabled,
  onTTSChange,
  className = ''
}) => {
  const { ttsEnabled, setTtsEnabled } = useTtsEnable()

  const handleToggle = useCallback((checked: boolean) => {
    setTtsEnabled(checked)
    onTTSChange?.(checked)
  }, [setTtsEnabled, onTTSChange])

  return (
    <BaseToggle
      checked={ttsEnabled}
      onChange={handleToggle}
      className={className}
      ariaLabel="Toggle text-to-speech"
      data-testid="tts-toggle"
    />
  )
}
