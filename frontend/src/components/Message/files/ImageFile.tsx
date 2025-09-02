import React from 'react'
import ImageWithVideoAction from '../../ImageWithVideoAction'

interface ImageFileProps {
  file: {
    name: string
    type: string
    data: string
  }
  onClick?: (imageUrl: string) => void
  sender: 'user' | 'bot'
}

/**
 * Image file display component.
 * 
 * Renders image files with click handling for viewer and optional action overlay
 * for bot messages. Prevents event bubbling to parent message handlers.
 * 
 * Args:
 *     file: Image file object with data URL
 *     onClick: Optional click handler for image viewer
 *     sender: Message sender type for action overlay logic
 * 
 * Returns:
 *     JSX element with clickable image and optional action overlay
 */
const ImageFile: React.FC<ImageFileProps> = ({ file, onClick, sender }) => {
  const handleImageClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    onClick?.(file.data)
  }
  
  return (
    <div className="file-preview">
      <div style={{ position: 'relative', display: 'inline-block' }}>
        <img 
          src={file.data} 
          alt={file.name} 
          className="file-image" 
          onClick={handleImageClick}
        />
        {sender === 'bot' && (
          <ImageWithVideoAction />
        )}
      </div>
    </div>
  )
}

export default ImageFile