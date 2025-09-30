/**
 * Type definitions for BackgroundTaskMonitor component.
 *
 * Defines the structure for background bash process monitoring,
 * mirroring backend notification data structure.
 */

/**
 * Background task status representation.
 *
 * Mirrors backend BackgroundProcess status for consistency.
 */
export interface BackgroundTask {
  process_id: string                    // Unique 6-char identifier
  command: string                       // Shell command
  description?: string                  // Optional description
  status: 'running' | 'completed' | 'killed'

  // Output display (last 5 lines)
  recent_output: string[]               // Recent output lines
  has_more_output: boolean              // More output available

  // Statistics
  runtime_seconds: number               // Process runtime
  exit_code?: number                    // Exit code when completed/killed

  // Metadata
  timestamp: string                     // Last update timestamp
}

/**
 * WebSocket notification event detail structure.
 *
 * Received from ConnectionContext custom events.
 */
export interface BackgroundProcessNotificationEvent {
  type: 'BACKGROUND_PROCESS_STARTED' |
        'BACKGROUND_PROCESS_OUTPUT_UPDATE' |
        'BACKGROUND_PROCESS_COMPLETED' |
        'BACKGROUND_PROCESS_KILLED'
  process_id: string
  command: string
  description?: string
  status: 'running' | 'completed' | 'killed'
  recent_output: string[]
  has_more_output: boolean
  runtime_seconds: number
  exit_code?: number
  session_id?: string
  timestamp: string
}