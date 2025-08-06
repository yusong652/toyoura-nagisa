import React from 'react';
import './ImagePreview.css';

interface ImagePreviewProps {
  open: boolean;
  onClose: () => void;
  imageUrl: string;
}

const ImagePreview: React.FC<ImagePreviewProps> = ({ open, onClose, imageUrl }) => {
  if (!open) return null;

  return (
    <div className="image-preview-overlay" onClick={onClose}>
      <div className="image-preview-container" onClick={e => e.stopPropagation()}>
        <button className="close-button" onClick={onClose}>×</button>
        <img src={imageUrl} alt="Preview" className="preview-image" />
      </div>
    </div>
  );
};

export default ImagePreview; 