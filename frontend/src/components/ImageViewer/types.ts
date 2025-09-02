/**
 * ImageViewer TypeScript type definitions.
 * 
 * Comprehensive type system for the advanced image viewer component,
 * following aiNagisa's clean architecture principles with clear separation
 * between state, events, and component interfaces.
 */

// =============================================================================
// Core Component Types
// =============================================================================

export interface ImageViewerProps {
  open: boolean
  onClose: () => void
  images: string[]
  initialIndex?: number
  imageNames?: string[]
}

export interface ImageInfo {
  url: string
  name?: string
  index: number
}

// =============================================================================
// Hook Return Types
// =============================================================================

export interface ImageViewerStateHookReturn {
  currentIndex: number
  setCurrentIndex: (index: number) => void
  zoom: number
  setZoom: (zoom: number | ((prev: number) => number)) => void
  pan: PanPosition
  setPan: (pan: PanPosition | ((prev: PanPosition) => PanPosition)) => void
  isLoading: boolean
  setIsLoading: (loading: boolean) => void
  currentImage: string
  hasMultipleImages: boolean
  getCurrentImageName: () => string
}

export interface ImageNavigationHookReturn {
  handlePrevImage: () => void
  handleNextImage: () => void
  canNavigatePrev: boolean
  canNavigateNext: boolean
}

export interface ImageZoomHookReturn {
  handleZoomIn: () => void
  handleZoomOut: () => void
  handleZoomReset: () => void
  canZoomIn: boolean
  canZoomOut: boolean
}

export interface ImageInteractionHookReturn {
  isDragging: boolean
  handleMouseDown: (e: React.MouseEvent) => void
  handleMouseMove: (e: React.MouseEvent) => void
  handleMouseUp: () => void
  handleWheel: (e: React.WheelEvent) => void
  handleTouchStart: (e: React.TouchEvent) => void
  handleTouchMove: (e: React.TouchEvent) => void
  handleTouchEnd: (e: React.TouchEvent) => void
  containerStyle: React.CSSProperties
  imageStyle: React.CSSProperties
}

export interface ThumbnailNavigationHookReturn {
  thumbnailStripRef: React.RefObject<HTMLDivElement>
  activeThumbnailRef: React.RefObject<HTMLButtonElement>
  scrollToActiveThumbnail: () => void
}

// =============================================================================
// Component-Specific Types
// =============================================================================

export interface ImageViewerHeaderProps {
  currentImageName: string
  currentIndex: number
  totalImages: number
  onClose: () => void
  hasMultipleImages: boolean
}

export interface ImageContainerProps {
  currentImage: string
  currentImageName: string
  isLoading: boolean
  zoom: number
  pan: PanPosition
  isDragging: boolean
  onImageLoad: () => void
  onImageError: () => void
  onMouseDown: (e: React.MouseEvent) => void
  onMouseMove: (e: React.MouseEvent) => void
  onMouseUp: () => void
  onMouseLeave: () => void
  onWheel: (e: React.WheelEvent) => void
  onTouchStart: (e: React.TouchEvent) => void
  onTouchMove: (e: React.TouchEvent) => void
  onTouchEnd: (e: React.TouchEvent) => void
  containerStyle: React.CSSProperties
  imageStyle: React.CSSProperties
}

export interface ImageControlsProps {
  zoom: number
  canZoomIn: boolean
  canZoomOut: boolean
  onZoomIn: () => void
  onZoomOut: () => void
  onZoomReset: () => void
}

export interface ImageNavigationProps {
  hasMultipleImages: boolean
  canNavigatePrev: boolean
  canNavigateNext: boolean
  onPrevImage: () => void
  onNextImage: () => void
}

export interface ThumbnailStripProps {
  images: string[]
  imageNames: string[]
  currentIndex: number
  onImageSelect: (index: number) => void
  thumbnailStripRef: React.RefObject<HTMLDivElement>
  activeThumbnailRef: React.RefObject<HTMLButtonElement>
}

export interface LoadingOverlayProps {
  isLoading: boolean
  message?: string
}

// =============================================================================
// Utility Types
// =============================================================================

export interface PanPosition {
  x: number
  y: number
}

export interface TouchState {
  x: number
  y: number
}

export interface DragState {
  x: number
  y: number
}

export interface ZoomConstraints {
  min: number
  max: number
  step: number
}

export interface SwipeGesture {
  threshold: number
  direction: 'left' | 'right' | 'up' | 'down' | null
  distance: number
}

export interface PinchGesture {
  initialDistance: number
  currentDistance: number
  scale: number
}

// =============================================================================
// Event Handler Types
// =============================================================================

export type ImageSelectHandler = (index: number) => void
export type ZoomChangeHandler = (zoom: number) => void
export type PanChangeHandler = (pan: PanPosition) => void
export type NavigationHandler = () => void
export type LoadStateHandler = (loading: boolean) => void

// =============================================================================
// Configuration Types
// =============================================================================

export interface ImageViewerConfig {
  zoomConstraints: ZoomConstraints
  swipeThreshold: number
  pinchSensitivity: number
  animationDuration: number
  preloadAdjacent: boolean
  enableKeyboardShortcuts: boolean
  enableTouchGestures: boolean
  enableMouseWheelZoom: boolean
}

// =============================================================================
// Constants
// =============================================================================

export const DEFAULT_ZOOM_CONSTRAINTS: ZoomConstraints = {
  min: 0.1,
  max: 5,
  step: 1.5
}

export const DEFAULT_SWIPE_THRESHOLD = 50

export const DEFAULT_PINCH_SENSITIVITY = 0.01

export const ANIMATION_DURATION = 200

// =============================================================================
// Type Guards and Utilities
// =============================================================================

export const isValidImageIndex = (index: number, totalImages: number): boolean => {
  return index >= 0 && index < totalImages
}

export const isValidZoom = (zoom: number, constraints: ZoomConstraints = DEFAULT_ZOOM_CONSTRAINTS): boolean => {
  return zoom >= constraints.min && zoom <= constraints.max
}

export const calculateZoomStep = (currentZoom: number, direction: 'in' | 'out', step: number = DEFAULT_ZOOM_CONSTRAINTS.step): number => {
  return direction === 'in' ? currentZoom * step : currentZoom / step
}

export const clampZoom = (zoom: number, constraints: ZoomConstraints = DEFAULT_ZOOM_CONSTRAINTS): number => {
  return Math.min(Math.max(zoom, constraints.min), constraints.max)
}