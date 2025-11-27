import React from 'react'
import { MessageRole } from '@aiNagisa/core'

interface ImageFileProps {
  file: {
    name: string
    type: string
    data: string
  }
  onClick?: (imageUrl: string) => void
  role: MessageRole
}

/**
 * Image file display component.
 *
 * Renders image files with click handling for viewer. Video generation
 * is now available via the /video slash command for better user experience.
 *
 * Args:
 *     file: Image file object with data URL
 *     onClick: Optional click handler for image viewer
 *     role: Message role type (kept for future extensibility)
 *
 * Returns:
 *     JSX element with clickable image
 */
const ImageFile: React.FC<ImageFileProps> = ({ file, onClick }) => {
  const handleImageClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onClick?.(file.data)
  }
  
  return (
    <div className="file-preview">
      <img 
        src={file.data} 
        alt={file.name} 
        className="file-image" 
        onClick={handleImageClick}
      />
      {/* Video generation is now available via /video slash command */}
    </div>
  )
}

export default ImageFile