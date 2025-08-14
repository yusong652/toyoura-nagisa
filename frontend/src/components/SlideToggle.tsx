import React from 'react';
import './SlideToggle.css';

interface SlideToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
  size?: 'small' | 'medium';
}

export const SlideToggle: React.FC<SlideToggleProps> = ({ 
  checked, 
  onChange, 
  disabled = false,
  size = 'small'
}) => {
  const handleToggle = () => {
    if (!disabled) {
      onChange(!checked);
    }
  };

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={handleToggle}
      disabled={disabled}
      className={`slide-toggle ${size} ${checked ? 'checked' : ''} ${disabled ? 'disabled' : ''}`}
    >
      <span className="slide-toggle-thumb"></span>
    </button>
  );
};