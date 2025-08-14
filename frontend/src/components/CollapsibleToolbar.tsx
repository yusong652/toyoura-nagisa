import React, { useState, useRef, useEffect } from 'react';
import { AgentProfileToggle } from './AgentProfileToggle';
import { TTSToggle } from './TTSToggle';
import { SlideToggle } from './SlideToggle';
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
                  <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                  <circle cx="12" cy="7" r="4" />
                </svg>
                <span className="toolbar-label">Agent Profile</span>
              </div>
              <AgentProfileToggle />
            </div>
          </div>
          
          <div className="toolbar-section">
            <div className="toolbar-item">
              <div className="toolbar-icon-label">
                <svg className="toolbar-section-icon" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                  <path d="M11 5L6 9H2v6h4l5 4V5z"/>
                  <path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/>
                </svg>
                <span className="toolbar-label">Text-to-Speech</span>
              </div>
              <TTSToggle />
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
              <SlideToggle
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