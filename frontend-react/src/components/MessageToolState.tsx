import React from 'react';
import './MessageToolState.css';

interface ToolState {
  isUsingTool: boolean;
  toolName?: string;
  action?: string;
}

interface MessageToolStateProps {
  toolState: ToolState;
}

const MessageToolState: React.FC<MessageToolStateProps> = ({ toolState }) => {
  const { isUsingTool, toolName, action } = toolState;

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