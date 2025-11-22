/**
 * Theme Toggle Component
 * 
 * Theme switcher with sun/moon icons, maintaining the original design.
 * Uses the traditional checkbox + label approach for compatibility.
 */

import React, { useState, useEffect, useCallback } from 'react'
import type { ThemeToggleProps } from '../types'
import './ThemeToggle.css'

export const ThemeToggle: React.FC<ThemeToggleProps> = ({
  onThemeChange,
  className = ''
}) => {
  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  // Initialize theme
  useEffect(() => {
    const savedTheme = (localStorage.getItem('theme') as 'light' | 'dark') || 'light'
    setTheme(savedTheme)
    document.body.setAttribute('data-theme', savedTheme)
  }, [])

  const toggleTheme = useCallback(() => {
    const newTheme = theme === 'light' ? 'dark' : 'light'
    setTheme(newTheme)
    document.body.setAttribute('data-theme', newTheme)
    localStorage.setItem('theme', newTheme)
    onThemeChange?.(newTheme)
  }, [theme, onThemeChange])

  return (
    <div className={`theme-toggle-container ${className}`}>
      <input
        type="checkbox"
        id="theme-toggle"
        className="theme-toggle-input"
        checked={theme === 'dark'}
        onChange={toggleTheme}
      />
      <label htmlFor="theme-toggle" className="theme-toggle-label">
        <span className="theme-toggle-slider" />
        <span className="theme-toggle-icon light">
          <svg 
            width="14" 
            height="14" 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="2" 
            strokeLinecap="round" 
            strokeLinejoin="round"
          >
            <circle cx="12" cy="12" r="5"/>
            <line x1="12" y1="1" x2="12" y2="3"/>
            <line x1="12" y1="21" x2="12" y2="23"/>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
            <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
            <line x1="1" y1="12" x2="3" y2="12"/>
            <line x1="21" y1="12" x2="23" y2="12"/>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
            <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
        </span>
        <span className="theme-toggle-icon dark">
          <svg 
            width="14" 
            height="14" 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="2" 
            strokeLinecap="round" 
            strokeLinejoin="round"
          >
            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
          </svg>
        </span>
      </label>
    </div>
  )
}

// For backward compatibility with default export
export default ThemeToggle