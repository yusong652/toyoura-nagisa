import React, { useState, useEffect } from 'react';
import './MessageToolState.css';
import { MessageToolState as MessageToolStateType } from '../types/chat';

interface MessageToolStateProps {
  toolState: MessageToolStateType;
}

const MessageToolState: React.FC<MessageToolStateProps> = ({ toolState }) => {
  const { isUsingTool, toolName, thinking } = toolState;
  const [displayedText, setDisplayedText] = useState('');
  const [isScrolling, setIsScrolling] = useState(false);
  const [animationDuration, setAnimationDuration] = useState(10);
  const [scrollDistance, setScrollDistance] = useState('-50%');

  if (!isUsingTool) return null;

  const thinkingContent = thinking || 'Processing...';
  
  useEffect(() => {
    if (!thinkingContent) {
      setDisplayedText('Processing...');
      return;
    }

    // Check content length for display decision
    const sentences = thinkingContent.split(/[.!?]+/).filter(s => s.trim().length > 0);
    const words = thinkingContent.split(' ');
    
    // For short content, display it directly without any processing
    if (words.length <= 40 || sentences.length <= 3) { // Increased threshold
      setDisplayedText(thinkingContent);
      setIsScrolling(false);
      return;
    }

    // For long content, keep it complete - no artificial line breaking
    // Just display the full content for scrolling
    setDisplayedText(thinkingContent);
    setIsScrolling(true);

    // Calculate scroll distance to show the end of content
    // Estimate content height based on character count and viewport
    const viewportHeight = 120; // Current viewport height in pixels
    const avgCharsPerLine = 50; // Approximate characters per line
    const lineHeight = 16.8; // font-size (12px) * line-height (1.4)
    
    const estimatedLines = Math.ceil(thinkingContent.length / avgCharsPerLine);
    const contentHeight = estimatedLines * lineHeight + 16; // +16 for padding
    
    // Calculate how much to scroll to show the end
    const scrollAmount = Math.max(0, contentHeight - viewportHeight);
    const scrollPercentage = (scrollAmount / contentHeight) * 100;
    
    setScrollDistance(`-${Math.min(scrollPercentage, 85)}%`); // Cap at 85% to always show some content
    
    // Calculate faster animation duration with accelerating effect based on content length
    const totalWords = words.length;
    const totalChars = thinkingContent.length;
    
    // Much faster base duration
    const baseDuration = 2; // Reduced from 4 to 2 seconds
    
    // Faster content-based factors
    const contentFactor = Math.min(totalWords * 0.05, 3); // Max 3 seconds from content (was 8)
    const charFactor = Math.min(totalChars * 0.01, 2); // Max 2 seconds from characters (was 4)
    
    // Total duration: much faster overall, capped at 8 seconds
    const duration = Math.min(baseDuration + contentFactor + charFactor, 8); // Max 8 seconds total (was 15)
    setAnimationDuration(duration);
  }, [thinkingContent]);

  return (
    <div className="message-tool-state">
      <div className="message-tool-state-content">
        <div className="message-tool-thinking-container">
          <div className="message-tool-thinking-viewport">
            {toolName && (
              <div className="message-tool-name">
                <div className="tool-name-icon"></div>
                <span className="tool-name-text">{toolName}</span>
              </div>
            )}
            <div 
              className={`message-tool-thinking-content ${isScrolling ? 'scrolling' : ''}`}
              style={{
                animationDuration: `${animationDuration}s`,
                '--scroll-end': scrollDistance
              } as React.CSSProperties}
            >
              {displayedText}
              {isScrolling && (
                <span className="thinking-dots">
                  <span className="dot dot-1">•</span>
                  <span className="dot dot-2">•</span>
                  <span className="dot dot-3">•</span>
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MessageToolState; 