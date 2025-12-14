/**
 * useTheme Hook
 * Subscribes to theme changes and triggers re-renders
 */

import { useState, useEffect, useCallback } from 'react';
import { themeManager, type ThemeName } from '../themes/index.js';

/**
 * Hook that subscribes to theme changes and provides theme utilities.
 * Components using this hook will re-render when the theme changes.
 */
export function useTheme() {
  // Use theme name as state to trigger re-renders
  const [themeName, setThemeName] = useState<ThemeName>(themeManager.getCurrentThemeName());

  useEffect(() => {
    // Subscribe to theme changes
    const unsubscribe = themeManager.subscribe(() => {
      setThemeName(themeManager.getCurrentThemeName());
    });

    return unsubscribe;
  }, []);

  const setTheme = useCallback((name: ThemeName) => {
    themeManager.setTheme(name);
  }, []);

  return {
    themeName,
    setTheme,
    availableThemes: themeManager.getAvailableThemes(),
  };
}
