/**
 * FileStorageAdapter - Node.js filesystem implementation
 *
 * Provides file-based storage for Node.js environments.
 * Implements the StorageAdapter interface for SessionManager.
 *
 * Note: This adapter requires Node.js 'fs/promises' module.
 * Will not work in browser environments.
 */

import { StorageAdapter } from '../SessionManager'

// Import will be resolved at runtime in Node.js environment
// Browser builds should not include this file
let fs: any
let path: any

try {
  // Dynamic import for Node.js modules (will fail in browser)
  fs = require('fs/promises')
  path = require('path')
} catch (error) {
  // Browser environment - fs and path will remain undefined
  console.warn('[FileStorageAdapter] Node.js modules not available (browser environment)')
}

/**
 * FileStorageAdapter - Node.js filesystem implementation
 *
 * Stores key-value pairs as JSON files in a directory.
 * Each key gets its own file: {storageDir}/{key}.json
 */
export class FileStorageAdapter implements StorageAdapter {
  private storageDir: string
  private initialized: boolean = false

  /**
   * Create a new FileStorageAdapter
   *
   * @param storageDir - Directory path for storage files
   */
  constructor(storageDir: string) {
    if (!fs || !path) {
      throw new Error('FileStorageAdapter requires Node.js environment')
    }
    this.storageDir = storageDir
  }

  /**
   * Ensure storage directory exists
   */
  private async ensureDir(): Promise<void> {
    if (this.initialized) return

    try {
      await fs.mkdir(this.storageDir, { recursive: true })
      this.initialized = true
    } catch (error) {
      console.error('[FileStorageAdapter] Failed to create storage directory:', error)
      throw error
    }
  }

  /**
   * Get file path for a key
   *
   * @param key - Storage key
   * @returns Full file path
   */
  private getFilePath(key: string): string {
    return path.join(this.storageDir, `${key}.json`)
  }

  /**
   * Get a value from file storage
   *
   * @param key - Storage key
   * @returns Promise resolving to stored value or null
   */
  async get(key: string): Promise<string | null> {
    await this.ensureDir()

    const filePath = this.getFilePath(key)
    try {
      const data = await fs.readFile(filePath, 'utf-8')
      return data
    } catch (error: any) {
      if (error.code === 'ENOENT') {
        // File doesn't exist
        return null
      }
      console.error('[FileStorageAdapter] Failed to read file:', error)
      return null
    }
  }

  /**
   * Set a value in file storage
   *
   * @param key - Storage key
   * @param value - Value to store
   */
  async set(key: string, value: string): Promise<void> {
    await this.ensureDir()

    const filePath = this.getFilePath(key)
    try {
      await fs.writeFile(filePath, value, 'utf-8')
    } catch (error) {
      console.error('[FileStorageAdapter] Failed to write file:', error)
      throw error
    }
  }

  /**
   * Remove a value from file storage
   *
   * @param key - Storage key
   */
  async remove(key: string): Promise<void> {
    await this.ensureDir()

    const filePath = this.getFilePath(key)
    try {
      await fs.unlink(filePath)
    } catch (error: any) {
      if (error.code === 'ENOENT') {
        // File doesn't exist - no error
        return
      }
      console.error('[FileStorageAdapter] Failed to remove file:', error)
      throw error
    }
  }

  /**
   * Clear all files from storage directory
   */
  async clear(): Promise<void> {
    await this.ensureDir()

    try {
      const files = await fs.readdir(this.storageDir)
      await Promise.all(
        files
          .filter((f: string) => f.endsWith('.json'))
          .map((f: string) => fs.unlink(path.join(this.storageDir, f)))
      )
    } catch (error) {
      console.error('[FileStorageAdapter] Failed to clear storage:', error)
      throw error
    }
  }
}
