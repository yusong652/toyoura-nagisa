/**
 * EventEmitter - Browser-compatible event emitter
 *
 * Lightweight event emitter implementation compatible with both browser and Node.js.
 * Provides a subset of Node.js EventEmitter API that's sufficient for our use cases.
 *
 * This implementation avoids dependency on Node.js 'events' module,
 * making it work seamlessly in browser environments.
 */

type EventListener = (...args: any[]) => void

/**
 * EventEmitter - Platform-agnostic event emitter
 *
 * Supports basic event emitter functionality:
 * - on() - Register event listener
 * - off() - Remove event listener
 * - emit() - Emit event
 * - once() - Register one-time listener
 * - removeAllListeners() - Remove all listeners for an event
 */
export class EventEmitter {
  private events: Map<string, EventListener[]> = new Map()

  /**
   * Register an event listener
   *
   * @param event - Event name
   * @param listener - Listener function
   * @returns this (for chaining)
   */
  on(event: string, listener: EventListener): this {
    if (!this.events.has(event)) {
      this.events.set(event, [])
    }
    this.events.get(event)!.push(listener)
    return this
  }

  /**
   * Remove an event listener
   *
   * @param event - Event name
   * @param listener - Listener function to remove
   * @returns this (for chaining)
   */
  off(event: string, listener: EventListener): this {
    const listeners = this.events.get(event)
    if (!listeners) return this

    const index = listeners.indexOf(listener)
    if (index !== -1) {
      listeners.splice(index, 1)
    }

    // Clean up empty listener arrays
    if (listeners.length === 0) {
      this.events.delete(event)
    }

    return this
  }

  /**
   * Register a one-time event listener
   *
   * Listener will be automatically removed after first invocation.
   *
   * @param event - Event name
   * @param listener - Listener function
   * @returns this (for chaining)
   */
  once(event: string, listener: EventListener): this {
    const onceWrapper: EventListener = (...args: any[]) => {
      this.off(event, onceWrapper)
      listener(...args)
    }
    return this.on(event, onceWrapper)
  }

  /**
   * Emit an event
   *
   * Calls all registered listeners for the event with provided arguments.
   *
   * @param event - Event name
   * @param args - Arguments to pass to listeners
   * @returns true if event had listeners, false otherwise
   */
  emit(event: string, ...args: any[]): boolean {
    const listeners = this.events.get(event)
    if (!listeners || listeners.length === 0) return false

    // Call each listener with arguments
    // Use slice() to avoid issues if listener modifies the array
    listeners.slice().forEach(listener => {
      try {
        listener(...args)
      } catch (error) {
        console.error(`[EventEmitter] Error in listener for event "${event}":`, error)
      }
    })

    return true
  }

  /**
   * Remove all listeners for an event
   *
   * If no event specified, removes all listeners for all events.
   *
   * @param event - Optional event name
   * @returns this (for chaining)
   */
  removeAllListeners(event?: string): this {
    if (event) {
      this.events.delete(event)
    } else {
      this.events.clear()
    }
    return this
  }

  /**
   * Get listener count for an event
   *
   * @param event - Event name
   * @returns Number of listeners
   */
  listenerCount(event: string): number {
    const listeners = this.events.get(event)
    return listeners ? listeners.length : 0
  }

  /**
   * Get all event names that have listeners
   *
   * @returns Array of event names
   */
  eventNames(): string[] {
    return Array.from(this.events.keys())
  }
}
