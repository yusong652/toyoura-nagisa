import React, { useState } from 'react';
import { IconButton } from '@mui/material';
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import { useSession } from '../contexts/session/SessionContext';
import { useChat } from '../contexts/chat/ChatContext';
import VideoPlayer from './VideoPlayer';
import UnifiedErrorDisplay from './UnifiedErrorDisplay';
import { useErrorDisplay } from '../hooks/useErrorDisplay';
import './ImageWithVideoAction.css';

interface ImageWithVideoActionProps {
  onVideoGenerated?: (videoUrl: string) => void;
}

const ImageWithVideoAction: React.FC<ImageWithVideoActionProps> = ({
  onVideoGenerated
}) => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [videoUrl] = useState<string | null>(null);
  const [showVideoPlayer, setShowVideoPlayer] = useState(false);
  const { currentSessionId } = useSession();
  const { generateVideo } = useChat();
  const { error, showTemporaryError, clearError } = useErrorDisplay();

  const handleGenerateVideo = async (e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (isGenerating || videoUrl) return;
    
    setIsGenerating(true);
    clearError();
    
    try {
      if (!currentSessionId) {
        showTemporaryError('No active session', 3000);
        return;
      }

      // Call the video generation API using the generateVideo hook
      const result = await generateVideo(currentSessionId);
      
      if (!result.success) {
        showTemporaryError(result.error || 'Failed to generate video', 5000);
      }
      
    } catch (err) {
      console.error('Error generating video:', err);
      showTemporaryError('Failed to generate video. Please try again.', 5000);
    } finally {
      setIsGenerating(false);
    }
  };

  const handlePlayVideo = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (videoUrl) {
      setShowVideoPlayer(true);
      if (onVideoGenerated) {
        onVideoGenerated(videoUrl);
      }
    }
  };

  return (
    <>
      <div className="image-video-action-container">
        {!videoUrl ? (
              <IconButton
                className="generate-video-button"
                onClick={handleGenerateVideo}
                disabled={isGenerating}
                size="small"
                sx={{
                  position: 'absolute',
                  bottom: 8,
                  right: 8,
                  backgroundColor: isGenerating ? 'rgba(138, 180, 248, 0.8)' : 'rgba(0, 0, 0, 0.6)',
                  color: 'white',
                  '&:hover': {
                    backgroundColor: isGenerating ? 'rgba(138, 180, 248, 0.9)' : 'rgba(0, 0, 0, 0.8)',
                  },
                  '&:disabled': {
                    backgroundColor: 'rgba(138, 180, 248, 0.7)',
                    color: 'white',
                  }
                }}
              >
                {isGenerating ? (
                  <div className="elegant-loading-container">
                    <div className="elegant-spinner" />
                    <div className="loading-pulse" />
                  </div>
                ) : (
                  <VideoLibraryIcon fontSize="small" />
                )}
              </IconButton>
        ) : (
            <IconButton
              className="play-video-button"
              onClick={handlePlayVideo}
              size="small"
              sx={{
                position: 'absolute',
                bottom: 8,
                right: 8,
                backgroundColor: 'rgba(0, 128, 0, 0.6)',
                color: 'white',
                '&:hover': {
                  backgroundColor: 'rgba(0, 128, 0, 0.8)',
                }
              }}
            >
              <PlayCircleOutlineIcon fontSize="small" />
            </IconButton>
        )}
      </div>
      
      <UnifiedErrorDisplay
        error={error}
        onClose={clearError}
      />
      
      {showVideoPlayer && videoUrl && (
        <VideoPlayer
          videoUrl={videoUrl}
          format="mp4"
          onClose={() => setShowVideoPlayer(false)}
          autoPlay={true}
          loop={true}
        />
      )}
    </>
  );
};

export default ImageWithVideoAction;