/**
 * Theme System
 * Supports multiple color schemes with runtime switching
 */

import { createRequire } from 'module';
const require = createRequire(import.meta.url);

export type ThemeName = 'github' | 'monokai' | 'dracula' | 'nord' | 'catppuccin' | 'everforest' | 'rosepine';

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

// Catppuccin Mocha theme (soft pastel colors)
const catppuccinColors: ThemeColors = {
  primary: '#89b4fa',    // Blue
  secondary: '#a6adc8',  // Subtext0
  accent: '#cba6f7',     // Mauve
  success: '#a6e3a1',    // Green
  error: '#f38ba8',      // Red
  warning: '#f9e2af',    // Yellow
  info: '#89dceb',       // Sky
  text: '#cdd6f4',       // Text
  textDim: '#bac2de',    // Subtext1
  textMuted: '#6c7086',  // Overlay0
  bg: '#1e1e2e',         // Base
  bgLight: '#313244',    // Surface0
  user: '#89dceb',       // Sky
  assistant: '#cdd6f4',  // Text
  system: '#6c7086',     // Overlay0
  tool: '#f9e2af',       // Yellow
  thinking: '#6c7086',   // Overlay0
};

// Everforest theme (green forest, easy on eyes)
const everforestColors: ThemeColors = {
  primary: '#a7c080',    // Green
  secondary: '#859289',  // Grey1
  accent: '#d699b6',     // Purple
  success: '#a7c080',    // Green
  error: '#e67e80',      // Red
  warning: '#dbbc7f',    // Yellow
  info: '#7fbbb3',       // Aqua
  text: '#d3c6aa',       // Fg
  textDim: '#9da9a0',    // Grey0
  textMuted: '#5c6a72',  // Grey2
  bg: '#2d353b',         // Bg0
  bgLight: '#3d484d',    // Bg1
  user: '#7fbbb3',       // Aqua
  assistant: '#d3c6aa',  // Fg
  system: '#5c6a72',     // Grey2
  tool: '#dbbc7f',       // Yellow
  thinking: '#5c6a72',   // Grey2
};

// Rose Pine theme (soft rose and pine colors)
const rosepineColors: ThemeColors = {
  primary: '#9ccfd8',    // Foam
  secondary: '#908caa',  // Subtle
  accent: '#c4a7e7',     // Iris
  success: '#9ccfd8',    // Foam
  error: '#eb6f92',      // Love
  warning: '#f6c177',    // Gold
  info: '#31748f',       // Pine
  text: '#e0def4',       // Text
  textDim: '#908caa',    // Subtle
  textMuted: '#6e6a86',  // Muted
  bg: '#191724',         // Base
  bgLight: '#26233a',    // Surface
  user: '#9ccfd8',       // Foam
  assistant: '#e0def4',  // Text
  system: '#6e6a86',     // Muted
  tool: '#f6c177',       // Gold
  thinking: '#6e6a86',   // Muted
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
  catppuccin: {
    name: 'catppuccin',
    displayName: 'Catppuccin',
    description: 'Soft pastel colors, easy on the eyes',
    colors: catppuccinColors,
    semantic: createSemanticTheme(catppuccinColors, ['#89b4fa', '#cba6f7', '#f38ba8']),
  },
  everforest: {
    name: 'everforest',
    displayName: 'Everforest',
    description: 'Green forest theme, nature-inspired',
    colors: everforestColors,
    semantic: createSemanticTheme(everforestColors, ['#a7c080', '#7fbbb3', '#d699b6']),
  },
  rosepine: {
    name: 'rosepine',
    displayName: 'Rosé Pine',
    description: 'Soft rose and pine colors',
    colors: rosepineColors,
    semantic: createSemanticTheme(rosepineColors, ['#9ccfd8', '#c4a7e7', '#eb6f92']),
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
