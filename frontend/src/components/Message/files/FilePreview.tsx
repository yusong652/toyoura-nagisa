import React from 'react'
import ImageFile from './ImageFile'
import VideoFile from './VideoFile'
import DocumentFile from './DocumentFile'
import { FilePreviewProps } from '../types'

/**
 * File preview dispatcher component.
 *
 * Routes file display to appropriate specialized components based on file type.
 * Handles images, videos, and generic documents with proper event handling.
 *
 * Args:
 *     file: File object with name, type, and data
 *     onImageClick: Optional image click handler
 *     onVideoClick: Optional video click handler
 *     role: Message role type for context
 *
 * Returns:
 *     JSX element with appropriate file preview component
 */
const FilePreview: React.FC<FilePreviewProps> = ({
  file,
  onImageClick,
  onVideoClick,
  role
}) => {
  const { type, name } = file
  
  // Image files
  if (type.startsWith('image/')) {
    return (
      <ImageFile
        file={file}
        onClick={onImageClick}
        role={role}
      />
    )
  }
  
  // Video files (by type or extension)
  const isVideo = type.startsWith('video/') || 
                 name.toLowerCase().endsWith('.mp4') ||
                 name.toLowerCase().endsWith('.gif') ||
                 name.toLowerCase().endsWith('.webm')
  
  if (isVideo) {
    return (
      <VideoFile 
        file={file}
        onClick={onVideoClick}
      />
    )
  }
  
  // Generic document files
  return (
    <DocumentFile 
      file={file}
    />
  )
}

export default FilePreview