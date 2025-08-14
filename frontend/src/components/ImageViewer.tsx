import React, { useState, useEffect, useCallback, useRef } from 'react';
import './ImageViewer.css';

interface ImageViewerProps {
  open: boolean;
  onClose: () => void;
  images: string[];
  initialIndex?: number;
  imageNames?: string[];
}

/**
 * Advanced image viewer component with zoom, pan, and navigation capabilities.
 * 
 * Features:
 * - Zoom in/out with mouse wheel or buttons
 * - Pan images when zoomed
 * - Navigate between multiple images
 * - Keyboard shortcuts (ESC, arrow keys, +/-)
 * - Touch gestures support
 * - Full screen viewing
 */
const ImageViewer: React.FC<ImageViewerProps> = ({ 
  open, 
  onClose, 
  images, 
  initialIndex = 0,
  imageNames = []
}) => {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [isLoading, setIsLoading] = useState(true);
  
  // Touch gesture states
  const [touchStart, setTouchStart] = useState({ x: 0, y: 0 });
  const [lastTouchDistance, setLastTouchDistance] = useState(0);
  const [swipeThreshold] = useState(50);
  
  const imageRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const thumbnailStripRef = useRef<HTMLDivElement>(null);
  const activeThumbnailRef = useRef<HTMLButtonElement>(null);

  // Reset state when opening/closing or changing image
  useEffect(() => {
    if (open) {
      setCurrentIndex(initialIndex);
      setZoom(1);
      setPan({ x: 0, y: 0 });
      setIsLoading(true);
    }
  }, [open, initialIndex]);

  // Reset zoom and pan when changing images
  useEffect(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setIsLoading(true);
  }, [currentIndex]);

  // Auto-scroll thumbnail strip to current image
  useEffect(() => {
    if (open && activeThumbnailRef.current && thumbnailStripRef.current && images.length > 1) {
      const thumbnail = activeThumbnailRef.current;
      const strip = thumbnailStripRef.current;
      
      // Use a small delay to ensure the DOM is fully rendered
      const scrollToThumbnail = () => {
        const thumbnailRect = thumbnail.getBoundingClientRect();
        const stripRect = strip.getBoundingClientRect();
        
        // Calculate scroll position to center the thumbnail
        const scrollLeft = thumbnail.offsetLeft - stripRect.width / 2 + thumbnailRect.width / 2;
        
        // Smooth scroll to the calculated position
        strip.scrollTo({
          left: Math.max(0, scrollLeft),
          behavior: open ? 'smooth' : 'auto' // No animation on initial load
        });
      };
      
      // Small delay to ensure proper rendering
      const timeoutId = setTimeout(scrollToThumbnail, 100);
      
      return () => clearTimeout(timeoutId);
    }
  }, [currentIndex, open, images.length]);

  // Keyboard event handlers
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!open) return;
    
    switch (e.key) {
      case 'Escape':
        onClose();
        break;
      case 'ArrowLeft':
        if (images.length > 1) {
          setCurrentIndex(prev => (prev - 1 + images.length) % images.length);
        }
        break;
      case 'ArrowRight':
        if (images.length > 1) {
          setCurrentIndex(prev => (prev + 1) % images.length);
        }
        break;
      case '=':
      case '+':
        e.preventDefault();
        handleZoomIn();
        break;
      case '-':
        e.preventDefault();
        handleZoomOut();
        break;
      case '0':
        handleZoomReset();
        break;
    }
  }, [open, images.length, onClose]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Prevent body scroll when viewer is open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
      return () => {
        document.body.style.overflow = '';
      };
    }
  }, [open]);

  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev * 1.5, 5));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev / 1.5, 0.1));
  };

  const handleZoomReset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleWheel = (e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      setZoom(prev => Math.min(Math.max(prev * delta, 0.1), 5));
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (zoom > 1) {
      setIsDragging(true);
      setDragStart({
        x: e.clientX - pan.x,
        y: e.clientY - pan.y
      });
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging && zoom > 1) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      });
    }
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  // Touch event handlers
  const getTouchDistance = (touches: React.TouchList) => {
    if (touches.length < 2) return 0;
    const touch1 = touches[0];
    const touch2 = touches[1];
    return Math.sqrt(
      Math.pow(touch2.clientX - touch1.clientX, 2) +
      Math.pow(touch2.clientY - touch1.clientY, 2)
    );
  };

  const handleTouchStart = (e: React.TouchEvent) => {
    if (e.touches.length === 1) {
      // Single touch - potential swipe
      const touch = e.touches[0];
      setTouchStart({ x: touch.clientX, y: touch.clientY });
    } else if (e.touches.length === 2) {
      // Two fingers - zoom gesture
      const distance = getTouchDistance(e.touches);
      setLastTouchDistance(distance);
    }
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    e.preventDefault();
    
    if (e.touches.length === 1) {
      // Single touch - check for swipe or pan
      const touch = e.touches[0];
      const deltaX = touch.clientX - touchStart.x;
      const deltaY = touch.clientY - touchStart.y;
      
      if (zoom > 1) {
        // Pan when zoomed
        setPan({
          x: pan.x + deltaX,
          y: pan.y + deltaY
        });
        setTouchStart({ x: touch.clientX, y: touch.clientY });
      }
    } else if (e.touches.length === 2) {
      const currentDistance = getTouchDistance(e.touches);
      
      // Check for zoom gesture
      const distanceChange = Math.abs(currentDistance - lastTouchDistance);
      
      // If distance change is significant, it's a zoom gesture
      if (distanceChange > 10) {
        const scale = currentDistance / lastTouchDistance;
        const newZoom = Math.min(Math.max(zoom * scale, 0.1), 5);
        setZoom(newZoom);
        setLastTouchDistance(currentDistance);
      }
    }
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    // Handle single finger swipe
    if (e.changedTouches.length === 1 && e.touches.length === 0) {
      const touch = e.changedTouches[0];
      const deltaX = touch.clientX - touchStart.x;
      const deltaY = touch.clientY - touchStart.y;
      
      // Only trigger swipe if horizontal movement is dominant and exceeds threshold
      if (Math.abs(deltaX) > swipeThreshold && Math.abs(deltaX) > Math.abs(deltaY) * 2 && zoom <= 1) {
        if (deltaX > 0 && images.length > 1) {
          // Swipe right - previous image
          handlePrevImage();
        } else if (deltaX < 0 && images.length > 1) {
          // Swipe left - next image
          handleNextImage();
        }
      }
    }
    
    // Reset touch states
    setLastTouchDistance(0);
  };

  const handleImageLoad = () => {
    setIsLoading(false);
  };

  const handlePrevImage = () => {
    if (images.length > 1) {
      setCurrentIndex(prev => (prev - 1 + images.length) % images.length);
    }
  };

  const handleNextImage = () => {
    if (images.length > 1) {
      setCurrentIndex(prev => (prev + 1) % images.length);
    }
  };

  const getCurrentImageName = () => {
    return imageNames[currentIndex] || `Image ${currentIndex + 1}`;
  };

  if (!open) return null;

  const currentImage = images[currentIndex];
  const hasMultipleImages = images.length > 1;

  return (
    <div className="image-viewer-overlay" onClick={onClose}>
      <div 
        className="image-viewer-container" 
        onClick={e => e.stopPropagation()}
        ref={containerRef}
      >
        {/* Header */}
        <div className="image-viewer-header">
          <div className="image-info">
            <span className="image-name">{getCurrentImageName()}</span>
            {hasMultipleImages && (
              <span className="image-counter">
                {currentIndex + 1} of {images.length}
              </span>
            )}
          </div>
          <button className="close-btn" onClick={onClose} aria-label="Close viewer">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* Main image container */}
        <div 
          className="image-container"
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onTouchStart={handleTouchStart}
          onTouchMove={handleTouchMove}
          onTouchEnd={handleTouchEnd}
          style={{ 
            cursor: zoom > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default',
            touchAction: 'none' // Prevent default touch behaviors
          }}
        >
          {isLoading && (
            <div className="image-loading">
              <div className="loading-spinner"></div>
              <span>Loading image...</span>
            </div>
          )}
          
          <img
            ref={imageRef}
            src={currentImage}
            alt={getCurrentImageName()}
            className="viewer-image"
            onLoad={handleImageLoad}
            onError={() => setIsLoading(false)}
            style={{
              transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
              transition: isDragging ? 'none' : 'transform 0.2s ease-out',
              opacity: isLoading ? 0 : 1
            }}
            draggable={false}
          />
        </div>

        {/* Navigation arrows */}
        {hasMultipleImages && (
          <>
            <button 
              className="nav-btn prev-btn" 
              onClick={handlePrevImage}
              aria-label="Previous image"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M15 18L9 12l6-6"/>
              </svg>
            </button>
            <button 
              className="nav-btn next-btn" 
              onClick={handleNextImage}
              aria-label="Next image"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 18l6-6-6-6"/>
              </svg>
            </button>
          </>
        )}

        {/* Controls */}
        <div className="image-controls">
          <button 
            className="control-btn" 
            onClick={handleZoomOut}
            disabled={zoom <= 0.1}
            aria-label="Zoom out"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
              <line x1="8" y1="12" x2="16" y2="12" stroke="currentColor" strokeWidth="2"/>
            </svg>
          </button>
          
          <span className="zoom-indicator">{Math.round(zoom * 100)}%</span>
          
          <button 
            className="control-btn" 
            onClick={handleZoomIn}
            disabled={zoom >= 5}
            aria-label="Zoom in"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
              <line x1="8" y1="12" x2="16" y2="12" stroke="currentColor" strokeWidth="2"/>
              <line x1="12" y1="8" x2="12" y2="16" stroke="currentColor" strokeWidth="2"/>
            </svg>
          </button>
          
          <button 
            className="control-btn" 
            onClick={handleZoomReset}
            aria-label="Reset zoom"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L12 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <path d="M12 18L12 22" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <path d="M22 12L18 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <path d="M6 12L2 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="2" fill="none"/>
            </svg>
          </button>
        </div>

        {/* Thumbnail strip for multiple images */}
        {hasMultipleImages && images.length > 1 && (
          <div className="thumbnail-strip" ref={thumbnailStripRef}>
            {images.map((image, index) => (
              <button
                key={index}
                ref={index === currentIndex ? activeThumbnailRef : null}
                className={`thumbnail ${index === currentIndex ? 'active' : ''}`}
                onClick={() => setCurrentIndex(index)}
                aria-label={`View image ${index + 1}`}
              >
                <img src={image} alt={`Thumbnail ${index + 1}`} />
              </button>
            ))}
          </div>
        )}

        {/* Keyboard shortcuts help */}
        <div className="keyboard-shortcuts">
          <div className="shortcuts-hint">
            Use arrow keys to navigate • Scroll or +/- to zoom • ESC to close
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImageViewer;