/**
 * Backend Process Manager
 * Automatically starts and manages the aiNagisa backend server
 */

import { spawn, ChildProcess } from 'child_process'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url)
const __dirname = dirname(__filename)

export class BackendManager {
  private process: ChildProcess | null = null
  private host: string
  private port: number
  private isReady: boolean = false

  constructor(host: string = 'localhost', port: number = 8000) {
    this.host = host
    this.port = port
  }

  /**
   * Start the backend server
   */
  async start(): Promise<void> {
    // Check if backend is already running
    const isRunning = await this.checkBackendHealth()
    if (isRunning) {
      console.log(`✅ Backend already running on ${this.host}:${this.port}`)
      this.isReady = true
      return
    }

    // Find project root (packages/cli/src/utils -> ../../../..)
    const projectRoot = resolve(__dirname, '../../../..')

    console.log(`🚀 Starting backend server...`)

    // Start backend process
    this.process = spawn('uv', ['run', 'python', 'backend/run.py'], {
      cwd: projectRoot,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1'
      },
      stdio: ['ignore', 'pipe', 'pipe']
    })

    // Handle backend output
    this.process.stdout?.on('data', (data: Buffer) => {
      const output = data.toString()
      // Only show important messages
      if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
        console.log(`[Backend] ${output.trim()}`)
      }
    })

    this.process.stderr?.on('data', (data: Buffer) => {
      const error = data.toString()
      if (!error.includes('DeprecationWarning') && !error.includes('FutureWarning')) {
        console.error(`[Backend Error] ${error.trim()}`)
      }
    })

    this.process.on('error', (err) => {
      console.error(`❌ Failed to start backend: ${err.message}`)
    })

    this.process.on('exit', (code) => {
      if (code !== 0 && code !== null) {
        console.error(`❌ Backend exited with code ${code}`)
      }
      this.isReady = false
    })

    // Wait for backend to be ready
    await this.waitForBackend()
    this.isReady = true
    console.log(`✅ Backend ready on http://${this.host}:${this.port}`)
  }

  /**
   * Check if backend is healthy
   */
  private async checkBackendHealth(): Promise<boolean> {
    try {
      const response = await fetch(`http://${this.host}:${this.port}/health`, {
        signal: AbortSignal.timeout(1000)
      })
      return response.ok
    } catch {
      return false
    }
  }

  /**
   * Wait for backend to be ready (max 30 seconds)
   */
  private async waitForBackend(): Promise<void> {
    const maxAttempts = 60 // 30 seconds with 500ms intervals
    let attempts = 0

    while (attempts < maxAttempts) {
      const isHealthy = await this.checkBackendHealth()
      if (isHealthy) {
        return
      }
      await new Promise(resolve => setTimeout(resolve, 500))
      attempts++
    }

    throw new Error('Backend failed to start within 30 seconds')
  }

  /**
   * Stop the backend server
   */
  stop(): void {
    if (this.process) {
      console.log('🛑 Stopping backend server...')
      this.process.kill('SIGTERM')
      this.process = null
      this.isReady = false
    }
  }

  /**
   * Check if backend is ready
   */
  ready(): boolean {
    return this.isReady
  }
}
