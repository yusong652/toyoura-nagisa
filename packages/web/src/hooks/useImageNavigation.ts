import { useMemo } from 'react';
import { Message, FileData } from '@toyoura-nagisa/core';

export interface ImageItem {
  url: string;
  name: string;
  messageId: string;
  messageIndex: number;
  fileIndex: number;
  timestamp: number;
}

export interface UseImageNavigationResult {
  allImages: ImageItem[];
  getImageIndex: (url: string) => number;
  getNextImage: (currentUrl: string) => ImageItem | null;
  getPreviousImage: (currentUrl: string) => ImageItem | null;
  getImageByIndex: (index: number) => ImageItem | null;
  totalImages: number;
}

/**
 * Custom hook for managing image navigation across all chat messages.
 * Provides utilities to navigate through all images in the conversation.
 */
export const useImageNavigation = (messages: Message[]): UseImageNavigationResult => {
  // Extract all images from messages and create navigation data
  const allImages = useMemo(() => {
    const images: ImageItem[] = [];
    
    messages.forEach((message, messageIndex) => {
      if (message.files && message.files.length > 0) {
        message.files.forEach((file: FileData, fileIndex: number) => {
          if (file.type.startsWith('image/')) {
            images.push({
              url: file.data,
              name: file.name,
              messageId: message.id,
              messageIndex,
              fileIndex,
              timestamp: message.timestamp
            });
          }
        });
      }
    });
    
    // Sort images by timestamp (oldest first)
    return images.sort((a, b) => a.timestamp - b.timestamp);
  }, [messages]);

  // Get the index of a specific image URL
  const getImageIndex = (url: string): number => {
    return allImages.findIndex(image => image.url === url);
  };

  // Get next image in sequence
  const getNextImage = (currentUrl: string): ImageItem | null => {
    const currentIndex = getImageIndex(currentUrl);
    if (currentIndex === -1 || currentIndex >= allImages.length - 1) {
      return null;
    }
    return allImages[currentIndex + 1];
  };

  // Get previous image in sequence
  const getPreviousImage = (currentUrl: string): ImageItem | null => {
    const currentIndex = getImageIndex(currentUrl);
    if (currentIndex <= 0) {
      return null;
    }
    return allImages[currentIndex - 1];
  };

  // Get image by index
  const getImageByIndex = (index: number): ImageItem | null => {
    if (index < 0 || index >= allImages.length) {
      return null;
    }
    return allImages[index];
  };

  return {
    allImages,
    getImageIndex,
    getNextImage,
    getPreviousImage,
    getImageByIndex,
    totalImages: allImages.length
  };
};