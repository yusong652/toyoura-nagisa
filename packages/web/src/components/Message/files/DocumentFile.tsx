import React from 'react'

interface DocumentFileProps {
  file: {
    name: string
    type: string
    data: string
  }
}

/**
 * Document file display component.
 * 
 * Renders generic document files with file icon, name, and size information.
 * Used for non-image, non-video files like PDFs, text files, etc.
 * 
 * Args:
 *     file: Document file object with metadata
 * 
 * Returns:
 *     JSX element with file icon, name, and size display
 */
const DocumentFile: React.FC<DocumentFileProps> = ({ file }) => {
  const fileSizeKB = (file.data.length / 1024).toFixed(1)
  
  return (
    <div className="file-preview">
      <div className="file-info">
        <span className="file-icon">📄</span>
        <span className="file-name">{file.name}</span>
        <span className="file-size">{fileSizeKB} KB</span>
      </div>
    </div>
  )
}

export default DocumentFile