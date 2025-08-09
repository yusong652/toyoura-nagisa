import React from 'react';
import './MessageToolState.css';
import { MessageToolState as MessageToolStateType } from '../types/chat';

interface MessageToolStateProps {
  toolState: MessageToolStateType;
}

const MessageToolState: React.FC<MessageToolStateProps> = ({ toolState }) => {
  const { isUsingTool, toolName, action } = toolState;

  console.log('[MessageToolState] Rendering with:', { isUsingTool, toolName, action });

  if (!isUsingTool) return null;

  return (
    <div className="message-tool-state">
      <div className="message-tool-state-content">
        <div className="message-tool-action">
          {action || 'using tool'}
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