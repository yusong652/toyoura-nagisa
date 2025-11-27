/**
 * Time formatting utilities for message timestamps
 *
 * Provides both relative time display (e.g., "5 minutes ago")
 * and absolute time formatting with locale support.
 *
 * @module @aiNagisa/core/utils/TimeFormatter
 * @author Nagisa Toyoura
 */

export interface TimeDisplayOptions {
  showRelative?: boolean
  locale?: string
  shortFormat?: boolean
}

/**
 * Format timestamp into relative time display
 *
 * @param timestamp - Unix timestamp in milliseconds
 * @returns Relative time string (e.g., "just now", "5 minutes ago")
 *
 * @example
 * ```typescript
 * getRelativeTime(Date.now() - 30000) // "just now"
 * getRelativeTime(Date.now() - 300000) // "5 minutes ago"
 * getRelativeTime(Date.now() - 7200000) // "2 hours ago"
 * ```
 */
export function getRelativeTime(timestamp: number): string {
  const now = Date.now()
  const diffMs = now - timestamp
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHour = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHour / 24)

  // Just now (< 30 seconds)
  if (diffSec < 30) {
    return 'just now'
  }

  // Minutes ago (< 60 minutes)
  if (diffMin < 60) {
    return diffMin === 1 ? '1 minute ago' : `${diffMin} minutes ago`
  }

  // Hours ago (< 24 hours)
  if (diffHour < 24) {
    return diffHour === 1 ? '1 hour ago' : `${diffHour} hours ago`
  }

  // Days ago (< 7 days)
  if (diffDay < 7) {
    return diffDay === 1 ? '1 day ago' : `${diffDay} days ago`
  }

  // For older messages, show absolute date
  const date = new Date(timestamp)
  return date.toLocaleDateString()
}

/**
 * Format timestamp into absolute time string
 *
 * @param timestamp - Unix timestamp in milliseconds
 * @param options - Formatting options
 * @returns Formatted time string
 *
 * @example
 * ```typescript
 * getAbsoluteTime(1700000000000) // "10:13 AM"
 * getAbsoluteTime(1700000000000, { shortFormat: false }) // "Nov 15, 2023, 10:13 AM"
 * ```
 */
export function getAbsoluteTime(timestamp: number, options: TimeDisplayOptions = {}): string {
  const { locale = 'en-US', shortFormat = true } = options
  const date = new Date(timestamp)

  if (shortFormat) {
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  return date.toLocaleString(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

/**
 * Smart time formatter that shows relative time for recent messages
 * and absolute time for older ones
 *
 * @param timestamp - Unix timestamp in milliseconds
 * @param options - Display options
 * @returns Formatted time string with full timestamp as title attribute data
 *
 * @example
 * ```typescript
 * // Recent message (< 24h)
 * formatSmartTime(Date.now() - 3600000)
 * // { display: "1 hour ago", fullTime: "Nov 25, 2023, 10:13 AM" }
 *
 * // Old message (> 24h)
 * formatSmartTime(Date.now() - 86400000 * 2)
 * // { display: "Nov 23, 2023, 10:13 AM", fullTime: "Nov 23, 2023, 10:13 AM" }
 * ```
 */
export function formatSmartTime(timestamp: number, options: TimeDisplayOptions = {}): {
  display: string
  fullTime: string
} {
  const { showRelative = true } = options
  const now = Date.now()
  const diffHours = (now - timestamp) / (1000 * 60 * 60)

  let display: string

  if (showRelative && diffHours < 24) {
    // Show relative time for messages within 24 hours
    display = getRelativeTime(timestamp)
  } else {
    // Show absolute time for older messages
    display = getAbsoluteTime(timestamp, options)
  }

  // Always provide full timestamp for tooltip
  const fullTime = getAbsoluteTime(timestamp, { ...options, shortFormat: false })

  return { display, fullTime }
}
