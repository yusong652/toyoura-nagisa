/**
 * CLI Color Definitions
 * Dynamic theme support with multiple color schemes
 */

import { themeManager, getTheme, getColors, type SemanticTheme, type ThemeColors } from './themes/index.js';

// Re-export theme utilities
export { themeManager, getTheme, getColors };
export type { SemanticTheme, ThemeColors };

// Dynamic theme proxy that always returns current theme colors
// This allows components to use `theme.text.primary` etc. and get the current theme's colors
export const theme: SemanticTheme = new Proxy({} as SemanticTheme, {
  get(_target, prop: string) {
    const currentTheme = getTheme();
    const value = currentTheme[prop as keyof SemanticTheme];

    // If the property is an object, return a proxy for it too
    if (typeof value === 'object' && value !== null) {
      return new Proxy(value, {
        get(_t, subProp: string) {
          // Always get fresh from current theme
          const freshTheme = getTheme();
          const freshValue = freshTheme[prop as keyof SemanticTheme];
          return (freshValue as Record<string, string>)[subProp];
        }
      });
    }
    return value;
  }
});

// Dynamic colors proxy
export const colors: ThemeColors = new Proxy({} as ThemeColors, {
  get(_target, prop: string) {
    return getColors()[prop as keyof ThemeColors];
  }
});
