import React from 'react';
import { useTtsEnable } from '../contexts/audio/TtsEnableContext';
import { SlideToggle } from './SlideToggle';
import UnifiedErrorDisplay from './UnifiedErrorDisplay';
import { useErrorDisplay } from '../hooks/useErrorDisplay';

export const TTSToggle: React.FC = () => {
  const { ttsEnabled, updateTTSEnabled } = useTtsEnable();
  const { error, showTemporaryError, clearError } = useErrorDisplay();

  const handleToggle = async (checked: boolean) => {
    try {
      await updateTTSEnabled(checked);
    } catch (error) {
      console.error('Failed to toggle TTS status:', error);
      showTemporaryError('Failed to toggle text-to-speech. Please try again.', 3000);
    }
  };

  return (
    <>
      <SlideToggle
        checked={ttsEnabled}
        onChange={handleToggle}
      />
      <UnifiedErrorDisplay
        error={error}
        onClose={clearError}
      />
    </>
  );
};