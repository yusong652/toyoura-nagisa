import React, { useState, useRef, useEffect } from 'react';
import { MemoryToggle } from './Toggle/variants/MemoryToggle';
import { ThinkingToggle } from './Toggle/variants/ThinkingToggle';
import { SettingsToggle } from './Toggle/variants/SettingsToggle';
import './CollapsibleToolbar.css';

export const CollapsibleToolbar: React.FC = () => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [settingsEnabled, setSettingsEnabled] = useState(false);
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
        title={isExpanded ? 'Collapse Toolbar' : 'Expand Toolbar'}
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
            <div className="toolbar-item">
              <div className="toolbar-icon-label">
                <svg className="toolbar-section-icon" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  {/* Memory icon - chip/circuit design */}
                  <rect x="4" y="4" width="16" height="16" rx="2" ry="2"/>
                  <rect x="9" y="9" width="6" height="6" rx="1" ry="1"/>
                  <path d="M9 1v6m6 0V1M9 17v6m6 0v-6m8-8h-6m0 6h6M7 9H1m6 6H1" strokeLinecap="round"/>
                </svg>
                <span className="toolbar-label">Memory</span>
              </div>
              <MemoryToggle />
            </div>
          </div>
          
          <div className="toolbar-section">
            <div className="toolbar-item">
              <div className="toolbar-icon-label">
                <svg className="toolbar-section-icon" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M12 1v6m0 10v6m11-7h-6M6 12H0" />
                </svg>
                <span className="toolbar-label">Settings</span>
              </div>
              <SettingsToggle
                checked={settingsEnabled}
                onChange={setSettingsEnabled}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
