import React, { useState } from 'react';
import { IconButton, Tooltip, CircularProgress, Snackbar, Alert } from '@mui/material';
import VideoLibraryIcon from '@mui/icons-material/VideoLibrary';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import { useSession } from '../contexts/session/SessionContext';
import { useChat } from '../contexts/chat/ChatContext';
import VideoPlayer from './VideoPlayer';
import { sessionService } from '../services/api/sessionService';
import { v4 as uuidv4 } from 'uuid';
import './ImageWithVideoAction.css';

interface ImageWithVideoActionProps {
  onVideoGenerated?: (videoUrl: string) => void;
}

const ImageWithVideoAction: React.FC<ImageWithVideoActionProps> = ({
  onVideoGenerated
}) => {
  const [isGenerating, setIsGenerating] = useState(false);
  const [videoUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showError, setShowError] = useState(false);
  const [showVideoPlayer, setShowVideoPlayer] = useState(false);
  const { currentSessionId } = useSession();
  const { addVideoMessage } = useChat();

  const handleGenerateVideo = async (e: React.MouseEvent) => {
    e.stopPropagation();
    
    if (isGenerating || videoUrl) return;
    
    setIsGenerating(true);
    setError(null);
    
    try {
      // Call the video generation API
      const response = await fetch('/api/generate-video', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: currentSessionId,
          motion_type: 'cinematic'
        }),
      });
      
      const result = await response.json();
      
      if (result.success && currentSessionId) {
        try {
          // 获取会话历史，查找最新的视频消息
          const historyData = await sessionService.getSessionHistory(currentSessionId);
          
          if (historyData.history && Array.isArray(historyData.history)) {
            const lastVideoMessage = historyData.history
              .filter((msg: any) => msg.role === 'video')
              .pop();

            if (lastVideoMessage) {
              // 直接添加视频消息到当前消息列表，与图片消息逻辑一致
              addVideoMessage(lastVideoMessage.video_path, lastVideoMessage.content || "🎬 视频已生成完成");
              console.log('Video message added to chat');
            }
          }
        } catch (error) {
          console.error('获取生成的视频消息失败:', error);
        }
      } else {
        setError(result.error || 'Failed to generate video');
        setShowError(true);
      }
      
    } catch (err) {
      console.error('Error generating video:', err);
      setError('Failed to generate video. Please try again.');
      setShowError(true);
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
          <Tooltip title={isGenerating ? "Generating video..." : "Generate video from image"}>
            <span>
              <IconButton
                className="generate-video-button"
                onClick={handleGenerateVideo}
                disabled={isGenerating}
                size="small"
                sx={{
                  position: 'absolute',
                  bottom: 8,
                  right: 8,
                  backgroundColor: 'rgba(0, 0, 0, 0.6)',
                  color: 'white',
                  '&:hover': {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                  },
                  '&:disabled': {
                    backgroundColor: 'rgba(0, 0, 0, 0.4)',
                    color: 'rgba(255, 255, 255, 0.5)',
                  }
                }}
              >
                {isGenerating ? (
                  <CircularProgress size={20} sx={{ color: 'white' }} />
                ) : (
                  <VideoLibraryIcon fontSize="small" />
                )}
              </IconButton>
            </span>
          </Tooltip>
        ) : (
          <Tooltip title="Play video">
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
          </Tooltip>
        )}
      </div>
      
      <Snackbar
        open={showError}
        autoHideDuration={6000}
        onClose={() => setShowError(false)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setShowError(false)} severity="error" sx={{ width: '100%' }}>
          {error}
        </Alert>
      </Snackbar>
      
      {showVideoPlayer && videoUrl && (
        <VideoPlayer
          videoUrl={videoUrl}
          format="mp4"
          onClose={() => setShowVideoPlayer(false)}
        />
      )}
    </>
  );
};

export default ImageWithVideoAction;