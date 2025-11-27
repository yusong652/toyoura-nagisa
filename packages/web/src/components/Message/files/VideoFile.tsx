import React from 'react'

interface VideoFileProps {
  file: {
    name: string
    type: string
    data: string
  }
  onClick?: (videoUrl: string, format: string) => void
}

/**
 * Video file display component.
 * 
 * Renders video files with elegant preview thumbnail and play button overlay.
 * Determines video format from file extension and handles click for video player.
 * 
 * Args:
 *     file: Video file object with data URL
 *     onClick: Optional click handler for video player
 * 
 * Returns:
 *     JSX element with video preview and play button overlay
 */
const VideoFile: React.FC<VideoFileProps> = ({ file, onClick }) => {
  const handleVideoClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    
    const fileName = file.name.toLowerCase()
    let format = 'mp4' // Default format
    
    if (fileName.endsWith('.gif')) {
      format = 'gif'
    } else if (fileName.endsWith('.webm')) {
      format = 'webm'
    } else if (fileName.endsWith('.mp4')) {
      format = 'mp4'
    }
    
    onClick?.(file.data, format)
  }
  
  const fileName = file.name.toLowerCase()
  const format = fileName.endsWith('.gif') ? 'gif' :
                fileName.endsWith('.webm') ? 'webm' : 'mp4'
  
  return (
    <div className="file-preview">
      <div 
        className="file-video-preview elegant-video" 
        onClick={handleVideoClick}
      >
        <video 
          src={file.data} 
          className="elegant-video-thumbnail"
          muted
          preload="metadata"
        />
        <div className="elegant-video-overlay">
          <div className="elegant-play-button">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z"/>
            </svg>
          </div>
        </div>
        <div className="elegant-video-info">
          <div className="video-format-badge">
            {format.toUpperCase()}
          </div>
        </div>
      </div>
    </div>
  )
}

export default VideoFile