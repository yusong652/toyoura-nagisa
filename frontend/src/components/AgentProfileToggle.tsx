import React from 'react';
import { useChat } from '../contexts/chat/ChatContext';

export const AgentProfileToggle: React.FC = () => {
  const { toolsEnabled, updateToolsEnabled } = useChat();

  const handleToggle = async () => {
    try {
      await updateToolsEnabled(!toolsEnabled);
    } catch (error) {
      console.error('切换Agent工具类型失败:', error);
    }
  };

  return (
    <button
      type="button"
      onClick={handleToggle}
      className={`agent-profile-toggle-btn${toolsEnabled ? ' active' : ''}`}
      title={toolsEnabled ? '关闭Agent工具' : '开启Agent工具'}
      aria-pressed={toolsEnabled}
    >
      {/* SVG icon for agent profile/persona */}
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    </button>
  );
}; 