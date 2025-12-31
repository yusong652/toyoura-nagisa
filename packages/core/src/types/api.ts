/**
 * API response types for toyoura-nagisa (2025 Standard).
 *
 * Defines the standard API response format used across all endpoints
 * for consistent client-side handling and type safety.
 */

/**
 * Standard API response wrapper.
 * All API endpoints return this format for consistent handling.
 *
 * @example
 * // Success response
 * {
 *   success: true,
 *   message: "Session created",
 *   data: { session_id: "abc-123" },
 *   error_code: null
 * }
 *
 * @example
 * // Error response (from HTTPException)
 * {
 *   detail: {
 *     error_code: "SESSION_NOT_FOUND",
 *     message: "Session 'abc-123' not found",
 *     details: { session_id: "abc-123" }
 *   }
 * }
 */
export interface ApiResponse<T> {
  success: boolean
  message: string
  data: T | null
  error_code: string | null
}

/**
 * Standard error response structure (inside HTTPException detail).
 */
export interface StandardErrorResponse {
  error_code: string
  message: string
  details?: Record<string, unknown>
}

/**
 * Type guard to check if a response is wrapped in ApiResponse format.
 *
 * @param obj - Response object to check
 * @returns True if object matches ApiResponse structure
 */
export function isApiResponse(obj: unknown): obj is ApiResponse<unknown> {
  return (
    typeof obj === 'object' &&
    obj !== null &&
    'success' in obj &&
    'data' in obj &&
    typeof (obj as ApiResponse<unknown>).success === 'boolean'
  )
}

/**
 * Error thrown when API returns success: false.
 * Contains the error details from the response for handling in catch blocks.
 */
export class ApiBusinessError extends Error {
  public readonly errorCode: string | null
  public readonly data: unknown

  constructor(message: string, errorCode: string | null, data: unknown) {
    super(message)
    this.name = 'ApiBusinessError'
    this.errorCode = errorCode
    this.data = data
  }
}

/**
 * Unwrap ApiResponse if needed, otherwise return as-is.
 * Provides backward compatibility during API migration.
 *
 * When success is false, throws ApiBusinessError to allow catch blocks
 * to handle business logic errors (e.g., PFC server not connected).
 *
 * @param response - Raw API response
 * @returns Unwrapped data or original response
 * @throws ApiBusinessError when success is false
 */
export function unwrapApiResponse<T>(response: unknown): T {
  if (isApiResponse(response)) {
    if (!response.success) {
      throw new ApiBusinessError(
        response.message,
        response.error_code,
        response.data
      )
    }
    return response.data as T
  }
  return response as T
}
