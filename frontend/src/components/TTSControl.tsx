import React from 'react';
import './TTSControl.css';
import { useChat } from '../contexts/ChatContext';

const TTSControl: React.FC = () => {
  const { ttsEnabled, updateTtsEnabled } = useChat();

  const handleToggle = async () => {
    try {
      await updateTtsEnabled(!ttsEnabled);
    } catch (error) {
      console.error('Failed to toggle TTS:', error);
    }
  };

  return (
    <div className="tts-control">
      <button 
        onClick={handleToggle} 
        className={`tts-button ${ttsEnabled ? 'enabled' : 'disabled'}`}
        title={ttsEnabled ? '关闭语音合成' : '开启语音合成'}
      >
        {ttsEnabled ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 5L6 9H2v6h4l5 4V5z"/>
            <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 5L6 9H2v6h4l5 4V5z"/>
            <line x1="23" y1="9" x2="17" y2="15"/>
            <line x1="17" y1="9" x2="23" y2="15"/>
          </svg>
        )}
      </button>
    </div>
  );
};

export default TTSControl; 