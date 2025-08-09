import React from 'react';
import './MessageToolState.css';
import { MessageToolState as MessageToolStateType } from '../types/chat';

interface MessageToolStateProps {
  toolState: MessageToolStateType;
}

const MessageToolState: React.FC<MessageToolStateProps> = ({ toolState }) => {
  const { isUsingTool, toolName, thinking } = toolState;

  if (!isUsingTool) return null;

  return (
    <div className="message-tool-state">
      <div className="message-tool-state-content">
        <div className="message-tool-thinking">
          {thinking || 'Processing...'}
        </div>
        {toolName && (
          <div className="message-tool-name">
            tool: {toolName}
          </div>
        )}
      </div>
    </div>
  );
};

export default MessageToolState; 