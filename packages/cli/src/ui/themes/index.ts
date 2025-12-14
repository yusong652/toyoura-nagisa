/**
 * Theme System
 * Supports multiple color schemes with runtime switching
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);

export type ThemeName = 'github' | 'monokai' | 'dracula' | 'nord';

export interface ThemeColors {
  // Primary colors
  primary: string;
  secondary: string;
  accent: string;

  // Status colors
  success: string;
  error: string;
  warning: string;
  info: string;

  // Text colors
  text: string;
  textDim: string;
  textMuted: string;

  // Background colors
  bg: string;
  bgLight: string;

  // Role colors
  user: string;
  assistant: string;
  system: string;
  tool: string;
  thinking: string;
}

export interface SemanticTheme {
  text: {
    primary: string;
    secondary: string;
    muted: string;
    accent: string;
    link: string;
    response: string;
  };
  status: {
    success: string;
    error: string;
    warning: string;
    info: string;
  };
  message: {
    user: string;
    assistant: string;
    system: string;
    tool: string;
    thinking: string;
  };
  ui: {
    border: string;
    borderFocus: string;
    spinner: string;
    symbol: string;
  };
  border: {
    default: string;
    focused: string;
  };
  /** Diff view background colors */
  diff: {
    addedBg: string;
    removedBg: string;
    addedText: string;
    removedText: string;
  };
  /** Gradient colors for header/branding */
  gradient: string[];
}

export interface ThemeDefinition {
  name: ThemeName;
  displayName: string;
  description: string;
  colors: ThemeColors;
  semantic: SemanticTheme;
}

// GitHub Dark theme
const githubColors: ThemeColors = {
  primary: '#58a6ff',
  secondary: '#8b949e',
  accent: '#a371f7',
  success: '#3fb950',
  error: '#f85149',
  warning: '#d29922',
  info: '#58a6ff',
  text: '#e6edf3',
  textDim: '#8b949e',
  textMuted: '#6e7681',
  bg: '#0d1117',
  bgLight: '#161b22',
  user: '#58a6ff',
  assistant: '#e6edf3',
  system: '#8b949e',
  tool: '#d29922',
  thinking: '#8b949e',
};

// Monokai theme (classic editor theme)
const monokaiColors: ThemeColors = {
  primary: '#66d9ef',    // Cyan
  secondary: '#75715e',  // Comment gray
  accent: '#ae81ff',     // Purple
  success: '#a6e22e',    // Green
  error: '#f92672',      // Pink/Red
  warning: '#e6db74',    // Yellow
  info: '#66d9ef',       // Cyan
  text: '#f8f8f2',       // Light
  textDim: '#a59f85',    // Dimmed
  textMuted: '#75715e',  // Muted
  bg: '#272822',         // Dark bg
  bgLight: '#3e3d32',    // Lighter bg
  user: '#66d9ef',       // Cyan
  assistant: '#f8f8f2',  // Light
  system: '#75715e',     // Gray
  tool: '#e6db74',       // Yellow
  thinking: '#75715e',   // Gray
};

// Dracula theme
const draculaColors: ThemeColors = {
  primary: '#bd93f9',    // Purple
  secondary: '#6272a4',  // Comment
  accent: '#ff79c6',     // Pink
  success: '#50fa7b',    // Green
  error: '#ff5555',      // Red
  warning: '#f1fa8c',    // Yellow
  info: '#8be9fd',       // Cyan
  text: '#f8f8f2',       // Foreground
  textDim: '#6272a4',    // Comment
  textMuted: '#44475a',  // Current line
  bg: '#282a36',         // Background
  bgLight: '#44475a',    // Current line
  user: '#8be9fd',       // Cyan
  assistant: '#f8f8f2',  // Light
  system: '#6272a4',     // Comment
  tool: '#f1fa8c',       // Yellow
  thinking: '#6272a4',   // Comment
};

// Nord theme (Arctic, north-bluish)
const nordColors: ThemeColors = {
  primary: '#88c0d0',    // Frost cyan
  secondary: '#4c566a',  // Polar night
  accent: '#b48ead',     // Aurora purple
  success: '#a3be8c',    // Aurora green
  error: '#bf616a',      // Aurora red
  warning: '#ebcb8b',    // Aurora yellow
  info: '#81a1c1',       // Frost blue
  text: '#eceff4',       // Snow storm
  textDim: '#d8dee9',    // Snow storm dimmed
  textMuted: '#4c566a',  // Polar night
  bg: '#2e3440',         // Polar night
  bgLight: '#3b4252',    // Polar night lighter
  user: '#88c0d0',       // Frost cyan
  assistant: '#eceff4',  // Snow storm
  system: '#4c566a',     // Polar night
  tool: '#ebcb8b',       // Aurora yellow
  thinking: '#4c566a',   // Polar night
};

interface DiffColors {
  addedBg: string;
  removedBg: string;
  addedText: string;
  removedText: string;
}

function createSemanticTheme(colors: ThemeColors, gradient?: string[], diff?: DiffColors): SemanticTheme {
  return {
    text: {
      primary: colors.text,
      secondary: colors.textDim,
      muted: colors.textMuted,
      accent: colors.accent,
      link: colors.primary,
      response: colors.text,
    },
    status: {
      success: colors.success,
      error: colors.error,
      warning: colors.warning,
      info: colors.info,
    },
    message: {
      user: colors.user,
      assistant: colors.text,
      system: colors.system,
      tool: colors.tool,
      thinking: colors.textMuted,
    },
    ui: {
      border: colors.textMuted,
      borderFocus: colors.primary,
      spinner: colors.primary,
      symbol: colors.textDim,
    },
    border: {
      default: colors.textMuted,
      focused: colors.primary,
    },
    diff: diff || {
      addedBg: '#145a24',      // Bright vivid green bg
      removedBg: '#8b2525',    // Bright vivid red bg
      addedText: colors.success,
      removedText: colors.error,
    },
    gradient: gradient || [colors.primary, colors.accent],
  };
}

// Theme definitions with custom gradients
export const themes: Record<ThemeName, ThemeDefinition> = {
  github: {
    name: 'github',
    displayName: 'GitHub Dark',
    description: 'GitHub-inspired dark theme with blue accents',
    colors: githubColors,
    semantic: createSemanticTheme(githubColors, ['#58a6ff', '#a371f7', '#f778ba']),
  },
  monokai: {
    name: 'monokai',
    displayName: 'Monokai',
    description: 'Classic editor theme with vibrant colors',
    colors: monokaiColors,
    semantic: createSemanticTheme(monokaiColors, ['#66d9ef', '#a6e22e', '#f92672']),
  },
  dracula: {
    name: 'dracula',
    displayName: 'Dracula',
    description: 'Dark theme with purple and pink accents',
    colors: draculaColors,
    semantic: createSemanticTheme(draculaColors, ['#bd93f9', '#ff79c6', '#8be9fd']),
  },
  nord: {
    name: 'nord',
    displayName: 'Nord',
    description: 'Arctic, north-bluish color palette',
    colors: nordColors,
    semantic: createSemanticTheme(nordColors, ['#88c0d0', '#81a1c1', '#b48ead']),
  },
};

// Theme manager for runtime switching
class ThemeManager {
  private currentThemeName: ThemeName = 'github';
  private listeners: Set<() => void> = new Set();
  private initialized = false;

  /**
   * Initialize theme from saved config
   * Should be called once at app startup
   */
  initialize(): void {
    if (this.initialized) return;
    this.initialized = true;

    try {
      // Dynamic import to avoid circular dependencies
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const { loadConfig } = require('../config/index.js') as { loadConfig: () => { theme?: ThemeName } };
      const config = loadConfig();
      if (config.theme && themes[config.theme]) {
        this.currentThemeName = config.theme;
      }
    } catch {
      // Config not available yet, use default
    }
  }

  getCurrentTheme(): ThemeDefinition {
    return themes[this.currentThemeName];
  }

  getCurrentThemeName(): ThemeName {
    return this.currentThemeName;
  }

  setTheme(name: ThemeName, persist = true): void {
    if (themes[name]) {
      this.currentThemeName = name;

      // Clear terminal screen and scrollback buffer (Static renders to main buffer with old colors)
      // \x1B[2J = clear visible screen, \x1B[3J = clear scrollback buffer, \x1B[H = move cursor home
      process.stdout.write('\x1B[2J\x1B[3J\x1B[H');

      this.notifyListeners();

      // Persist to config file
      if (persist) {
        try {
          const { setConfigValue } = require('../config/index.js');
          setConfigValue('theme', name);
        } catch {
          // Config not available, skip persistence
        }
      }
    }
  }

  getAvailableThemes(): ThemeName[] {
    return Object.keys(themes) as ThemeName[];
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notifyListeners(): void {
    this.listeners.forEach((listener) => listener());
  }
}

export const themeManager = new ThemeManager();

// Dynamic theme accessor (use this in components)
export function getTheme(): SemanticTheme {
  return themeManager.getCurrentTheme().semantic;
}

export function getColors(): ThemeColors {
  return themeManager.getCurrentTheme().colors;
}
