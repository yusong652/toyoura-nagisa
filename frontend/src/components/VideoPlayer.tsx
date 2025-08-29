import React, { useEffect, useRef } from 'react';
import './VideoPlayer.css';

interface VideoPlayerProps {
  videoUrl: string;
  format?: string;
  onClose: () => void;
}

const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoUrl, format = 'mp4', onClose }) => {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    // Handle escape key to close video
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onClose]);

  const handleBackgroundClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  // Convert base64 to blob URL if needed
  const getVideoSource = () => {
    if (videoUrl.startsWith('data:video') || videoUrl.startsWith('data:image/gif')) {
      return videoUrl;
    }
    if (videoUrl.includes('base64')) {
      return `data:video/${format};base64,${videoUrl}`;
    }
    return videoUrl;
  };

  return (
    <div className="video-player-overlay" onClick={handleBackgroundClick}>
      <div className="video-player-container">
        <button className="video-close-button" onClick={onClose}>
          ×
        </button>
        {format === 'gif' ? (
          <img 
            src={getVideoSource()} 
            alt="Generated animation"
            className="video-gif"
          />
        ) : (
          <video
            ref={videoRef}
            src={getVideoSource()}
            controls
            autoPlay
            loop
            className="video-element"
          />
        )}
      </div>
    </div>
  );
};

export default VideoPlayer;