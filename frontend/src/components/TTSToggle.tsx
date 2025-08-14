import React from 'react';
import { useChat } from '../contexts/chat/ChatContext';

export const TTSToggle: React.FC = () => {
  const { ttsEnabled, updateTtsEnabled } = useChat();

  const handleToggle = async () => {
    try {
      await updateTtsEnabled(!ttsEnabled);
    } catch (error) {
      console.error('切换TTS状态失败:', error);
    }
  };

  return (
    <button
      type="button"
      onClick={handleToggle}
      className={`tts-toggle-btn${ttsEnabled ? ' enabled' : ' disabled'}`}
      title={ttsEnabled ? '关闭语音合成' : '开启语音合成'}
      aria-pressed={ttsEnabled}
    >
      {ttsEnabled ? (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path d="M11 5L6 9H2v6h4l5 4V5z"/>
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>
        </svg>
      ) : (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <path d="M11 5L6 9H2v6h4l5 4V5z"/>
          <line x1="23" y1="9" x2="17" y2="15"/>
          <line x1="17" y1="9" x2="23" y2="15"/>
        </svg>
      )}
    </button>
  );
};