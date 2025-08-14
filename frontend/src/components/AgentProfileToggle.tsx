import React from 'react';
import { useChat } from '../contexts/chat/ChatContext';
import { SlideToggle } from './SlideToggle';

export const AgentProfileToggle: React.FC = () => {
  const { toolsEnabled, updateToolsEnabled } = useChat();

  const handleToggle = async (checked: boolean) => {
    try {
      await updateToolsEnabled(checked);
    } catch (error) {
      console.error('切换Agent工具类型失败:', error);
    }
  };

  return (
    <SlideToggle
      checked={toolsEnabled}
      onChange={handleToggle}
    />
  );
}; 