import React from 'react';
import { useChat } from '../contexts/chat/ChatContext';
import { SlideToggle } from './SlideToggle';

export const TTSToggle: React.FC = () => {
  const { ttsEnabled, updateTtsEnabled } = useChat();

  const handleToggle = async (checked: boolean) => {
    try {
      await updateTtsEnabled(checked);
    } catch (error) {
      console.error('切换TTS状态失败:', error);
    }
  };

  return (
    <SlideToggle
      checked={ttsEnabled}
      onChange={handleToggle}
    />
  );
};