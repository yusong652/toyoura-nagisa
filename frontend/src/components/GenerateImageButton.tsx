import React, { useState } from 'react';
import './GenerateImageButton.css';
import { useChat } from '../contexts/chat/ChatContext';
import { useSession } from '../contexts/session/SessionContext';

const GenerateImageButton: React.FC = () => {
  const { generateImage } = useChat();
  const { currentSessionId } = useSession();
  const [loading, setLoading] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  const handleClick = async () => {
    if (!currentSessionId) return;
    setLoading(true);
    setShowSuccess(false);
    try {
      const res = await generateImage(currentSessionId);
      if (res.success) {
        setShowSuccess(true);
        // 不再需要 switchSession，因为图片已在 generateImage 中直接添加到消息列表
        setTimeout(() => setShowSuccess(false), 2000);
      }
    } catch (e: any) {
      console.error('Failed to generate image:', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="generate-image-btn-wrapper">
      <button
        className={`generate-image-btn ${showSuccess ? 'success' : ''}`}
        onClick={handleClick}
        disabled={loading || !currentSessionId}
        title="生成图片"
      >
        {loading ? (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="generate-image-spinner">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 6v2" />
          </svg>
        ) : showSuccess ? (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 6L9 17l-5-5" />
          </svg>
        ) : (
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <path d="M21 15l-5-5L5 21" />
          </svg>
        )}
      </button>
    </div>
  );
};

export default GenerateImageButton; 