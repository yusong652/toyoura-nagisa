import React from 'react'
import { MessageRole } from '@toyoura-nagisa/core'

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
 * Renders image files with click handling for viewer.
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
    </div>
  )
}

export default ImageFile
