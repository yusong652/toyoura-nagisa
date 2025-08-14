import React, { useState, useRef, useEffect } from 'react';
import { AgentProfileToggle } from './AgentProfileToggle';
import { TTSToggle } from './TTSToggle';
import './CollapsibleToolbar.css';

export const CollapsibleToolbar: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState(false);
  const toolbarRef = useRef<HTMLDivElement>(null);

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded);
  };

  // Handle clicks outside the toolbar to collapse it
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (toolbarRef.current && !toolbarRef.current.contains(event.target as Node)) {
        setIsExpanded(false);
      }
    };

    if (isExpanded) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isExpanded]);

  return (
    <div className="collapsible-toolbar" ref={toolbarRef}>
      <button
        type="button"
        onClick={toggleExpanded}
        className={`toolbar-toggle-btn${isExpanded ? ' expanded' : ''}`}
        title={isExpanded ? '收起工具栏' : '展开工具栏'}
        aria-expanded={isExpanded}
      >
        {/* Hamburger menu icon */}
        <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
          <line x1="3" y1="6" x2="21" y2="6" />
          <line x1="3" y1="12" x2="21" y2="12" />
          <line x1="3" y1="18" x2="21" y2="18" />
        </svg>
      </button>
      
      {isExpanded && (
        <div className="toolbar-content">
          <div className="toolbar-section">
            <span className="toolbar-label">Agent设置</span>
            <AgentProfileToggle />
          </div>
          
          <div className="toolbar-section">
            <span className="toolbar-label">语音控制</span>
            <div className="toolbar-options">
              <TTSToggle />
            </div>
          </div>
          
          <div className="toolbar-section">
            <span className="toolbar-label">更多选项</span>
            <div className="toolbar-options">
              <button className="toolbar-option-btn" title="设置">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M12 1v6m0 10v6m11-7h-6M6 12H0" />
                </svg>
              </button>
              <button className="toolbar-option-btn" title="帮助">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};