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

  if (!isUsingTool) return null;

  const thinkingContent = thinking || 'Processing...';
  
  useEffect(() => {
    if (!thinkingContent) {
      setDisplayedText('Processing...');
      return;
    }

    // Split content into words for better line wrapping
    const words = thinkingContent.split(' ');
    
    // Create "lines" by grouping words (approximately 7-9 words per line for larger viewport)
    const linesData: string[] = [];
    const wordsPerLine = 8; // Increased for better utilization of larger viewport
    
    for (let i = 0; i < words.length; i += wordsPerLine) {
      const lineWords = words.slice(i, i + wordsPerLine);
      linesData.push(lineWords.join(' '));
    }

    // For short content, just display it (show up to 5 lines before scrolling)
    if (linesData.length <= 5) {
      setDisplayedText(linesData.join('\n'));
      setIsScrolling(false);
      return;
    }

    // For long content, create continuous scrolling text
    // Create multiple repetitions with separators for smooth scrolling
    const repetitions = Math.max(4, Math.ceil(20 / linesData.length)); // Ensure enough content height for larger viewport
    const extendedLines: string[] = [];
    
    for (let i = 0; i < repetitions; i++) {
      extendedLines.push(...linesData);
      if (i < repetitions - 1) {
        extendedLines.push(''); // Add separator line between repetitions
      }
    }
    
    setDisplayedText(extendedLines.join('\n'));
    setIsScrolling(true);
    
    // Calculate animation duration: optimized for larger viewport
    const duration = Math.max(4, linesData.length * 1.2); // 1.2 seconds per line for smooth, premium feel
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
                animationDuration: `${animationDuration}s`
              }}
            >
              {displayedText}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MessageToolState; 