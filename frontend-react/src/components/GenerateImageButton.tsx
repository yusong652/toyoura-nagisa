import React, { useState } from 'react';
import './GenerateImageButton.css';
import { useChat } from '../contexts/ChatContext';

const CHECK_DISPLAY_TIME = 3600; // ms

const GenerateImageButton: React.FC = () => {
  const { generateImage, currentSessionId } = useChat();
  const [loading, setLoading] = useState(false);
  const [showCheck, setShowCheck] = useState(false);

  const handleClick = async () => {
    if (!currentSessionId) return;
    setLoading(true);
    setShowCheck(false);
    try {
      const res = await generateImage(currentSessionId);
      setLoading(false);
      if (res.success) {
        setShowCheck(true);
        setTimeout(() => setShowCheck(false), CHECK_DISPLAY_TIME);
      }
      // No error UI
    } catch (e: any) {
      setLoading(false);
    }
  };

  return (
    <div className="generate-image-btn-wrapper">
      <button
        className="generate-image-btn"
        onClick={handleClick}
        disabled={loading || !currentSessionId}
        aria-label="Generate Image"
        title="Generate Image"
      >
        {loading ? (
          <svg className="generate-image-spinner" width="22" height="22" viewBox="0 0 50 50">
            <circle
              className="generate-image-spinner-circle"
              cx="25" cy="25" r="12" fill="none" stroke="#fff" strokeWidth="4" strokeDasharray="90 60" strokeLinecap="round"
            />
          </svg>
        ) : showCheck ? (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2ecc40" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 10.8 17 4 11" />
          </svg>
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M16 4l4 4-12 12H4v-4L16 4z"/>
            <path d="M15 9l-1 1"/>
          </svg>
        )}
      </button>
    </div>
  );
};

export default GenerateImageButton; 