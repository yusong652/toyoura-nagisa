/**
 * LocalStorageAdapter - Browser localStorage implementation
 *
 * Provides localStorage-based storage for browser environments.
 * Implements the StorageAdapter interface for SessionManager.
 */

import { StorageAdapter } from '../SessionManager'

/**
 * LocalStorageAdapter - Browser localStorage implementation
 *
 * Uses browser's localStorage API for persistent storage.
 */
export class LocalStorageAdapter implements StorageAdapter {
  private prefix: string

  /**
   * Create a new LocalStorageAdapter
   *
   * @param prefix - Optional prefix for all storage keys (default: 'aiNagisa_')
   */
  constructor(prefix: string = 'aiNagisa_') {
    this.prefix = prefix
  }

  /**
   * Get prefixed key
   *
   * @param key - Original key
   * @returns Prefixed key
   */
  private getPrefixedKey(key: string): string {
    return `${this.prefix}${key}`
  }

  /**
   * Get a value from localStorage
   *
   * @param key - Storage key
   * @returns Promise resolving to stored value or null
   */
  async get(key: string): Promise<string | null> {
    try {
      return localStorage.getItem(this.getPrefixedKey(key))
    } catch (error) {
      console.error('[LocalStorageAdapter] Failed to get item:', error)
      return null
    }
  }

  /**
   * Set a value in localStorage
   *
   * @param key - Storage key
   * @param value - Value to store
   */
  async set(key: string, value: string): Promise<void> {
    try {
      localStorage.setItem(this.getPrefixedKey(key), value)
    } catch (error) {
      console.error('[LocalStorageAdapter] Failed to set item:', error)
      throw error
    }
  }

  /**
   * Remove a value from localStorage
   *
   * @param key - Storage key
   */
  async remove(key: string): Promise<void> {
    try {
      localStorage.removeItem(this.getPrefixedKey(key))
    } catch (error) {
      console.error('[LocalStorageAdapter] Failed to remove item:', error)
      throw error
    }
  }

  /**
   * Clear all prefixed values from localStorage
   *
   * Only removes keys with the configured prefix.
   */
  async clear(): Promise<void> {
    try {
      const keys = Object.keys(localStorage)
      for (const key of keys) {
        if (key.startsWith(this.prefix)) {
          localStorage.removeItem(key)
        }
      }
    } catch (error) {
      console.error('[LocalStorageAdapter] Failed to clear storage:', error)
      throw error
    }
  }
}
