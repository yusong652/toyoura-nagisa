/**
 * CLI Configuration Management
 * Persists user preferences (theme, etc.) to config.json in CLI root
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import type { ThemeName } from '../themes/index.js';

// Get CLI package root directory
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
// Navigate from dist/ui/config to package root (3 levels up)
const CLI_ROOT = join(__dirname, '..', '..', '..');
const CONFIG_FILE = join(CLI_ROOT, 'config.json');

export interface CLIConfig {
  theme: ThemeName;
}

const DEFAULT_CONFIG: CLIConfig = {
  theme: 'github',
};

/**
 * Load configuration from config.json
 */
export function loadConfig(): CLIConfig {
  try {
    if (existsSync(CONFIG_FILE)) {
      const content = readFileSync(CONFIG_FILE, 'utf-8');
      const config = JSON.parse(content) as Partial<CLIConfig>;
      return {
        ...DEFAULT_CONFIG,
        ...config,
      };
    }
  } catch (error) {
    // Ignore errors, use defaults
  }
  return DEFAULT_CONFIG;
}

/**
 * Save configuration to config.json
 */
export function saveConfig(config: Partial<CLIConfig>): void {
  try {
    const currentConfig = loadConfig();
    const newConfig = {
      ...currentConfig,
      ...config,
    };
    writeFileSync(CONFIG_FILE, JSON.stringify(newConfig, null, 2) + '\n', 'utf-8');
  } catch (error) {
    // Silently fail - config saving is not critical
    console.error('Failed to save config:', error);
  }
}

/**
 * Get a specific config value
 */
export function getConfigValue<K extends keyof CLIConfig>(key: K): CLIConfig[K] {
  return loadConfig()[key];
}

/**
 * Set a specific config value
 */
export function setConfigValue<K extends keyof CLIConfig>(key: K, value: CLIConfig[K]): void {
  saveConfig({ [key]: value });
}
