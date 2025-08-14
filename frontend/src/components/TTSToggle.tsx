import React from 'react';
import { useTtsEnable } from '../contexts/audio/TtsEnableContext';
import { SlideToggle } from './SlideToggle';

export const TTSToggle: React.FC = () => {
  const { ttsEnabled, updateTTSEnabled } = useTtsEnable();

  const handleToggle = async (checked: boolean) => {
    try {
      await updateTTSEnabled(checked);
    } catch (error) {
      console.error('Failed to toggle TTS status:', error);
    }
  };

  return (
    <SlideToggle
      checked={ttsEnabled}
      onChange={handleToggle}
    />
  );
};