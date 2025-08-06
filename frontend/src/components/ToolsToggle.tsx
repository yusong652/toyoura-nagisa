import React from 'react';
import { useChat } from '../contexts/ChatContext';

export const ToolsToggle: React.FC = () => {
  const { toolsEnabled, updateToolsEnabled } = useChat();

  const handleToggle = async () => {
    try {
      await updateToolsEnabled(!toolsEnabled);
    } catch (error) {
      console.error('切换工具状态失败:', error);
    }
  };

  return (
    <button
      type="button"
      onClick={handleToggle}
      className={`tools-toggle-btn${toolsEnabled ? ' active' : ''}`}
      title={toolsEnabled ? '关闭工具' : '开启工具'}
      aria-pressed={toolsEnabled}
    >
      {/* SVG icon for settings/tune */}
      <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" fill="none" />
        <path d="M12 6v2m0 8v2m6-6h-2M8 12H6m8.49-4.49l-1.42 1.42M8.93 15.07l-1.42 1.42m0-9.9l1.42 1.42m7.07 7.07l1.42 1.42" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      </svg>
    </button>
  );
}; 