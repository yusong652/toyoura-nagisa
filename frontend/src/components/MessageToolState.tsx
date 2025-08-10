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
    
    // Create "lines" by grouping words (approximately 6-8 words per line)
    const linesData: string[] = [];
    const wordsPerLine = 6;
    
    for (let i = 0; i < words.length; i += wordsPerLine) {
      const lineWords = words.slice(i, i + wordsPerLine);
      linesData.push(lineWords.join(' '));
    }

    // For short content, just display it
    if (linesData.length <= 3) {
      setDisplayedText(linesData.join('\n'));
      setIsScrolling(false);
      return;
    }

    // For long content, create continuous scrolling text
    // Create multiple repetitions with separators for smooth scrolling
    const repetitions = Math.max(4, Math.ceil(15 / linesData.length)); // Ensure enough content height
    const extendedLines: string[] = [];
    
    for (let i = 0; i < repetitions; i++) {
      extendedLines.push(...linesData);
      if (i < repetitions - 1) {
        extendedLines.push(''); // Add separator line between repetitions
      }
    }
    
    setDisplayedText(extendedLines.join('\n'));
    setIsScrolling(true);
    
    // Calculate animation duration: faster for testing, slower for production
    const duration = Math.max(3, linesData.length * 1); // 1 second per line for visible effect
    setAnimationDuration(duration);
  }, [thinkingContent]);

  return (
    <div className="message-tool-state">
      <div className="message-tool-state-content">
        {toolName && (
          <div className="message-tool-name">
            {toolName}
          </div>
        )}
        
        <div className="message-tool-thinking-container">
          <div className="message-tool-thinking-viewport">
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