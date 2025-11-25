/**
 * HTTP client utility for making API requests with consistent error handling.
 * 
 * Provides a standardized interface for HTTP operations with proper error
 * handling, request/response logging, and type safety for aiNagisa frontend.
 */

export interface ApiError extends Error {
  status: number
  response?: any
}

export class HttpClient {
  private baseURL: string

  constructor(baseURL: string = '') {
    this.baseURL = baseURL
  }

  /**
   * Set the base URL for all requests.
   *
   * @param baseURL - The base URL to use
   */
  setBaseURL(baseURL: string): void {
    this.baseURL = baseURL
  }

  /**
   * Get the current base URL.
   *
   * @returns The current base URL
   */
  getBaseURL(): string {
    return this.baseURL
  }

  /**
   * Make a GET request to the specified endpoint.
   * 
   * @param url - The endpoint URL
   * @param options - Optional fetch configuration
   * @returns Promise resolving to parsed JSON response
   */
  async get<T>(url: string, options: RequestInit = {}): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: 'GET'
    })
  }

  /**
   * Make a POST request to the specified endpoint.
   * 
   * @param url - The endpoint URL
   * @param data - Request payload to be JSON serialized
   * @param options - Optional fetch configuration
   * @returns Promise resolving to parsed JSON response
   */
  async post<T>(url: string, data?: any, options: RequestInit = {}): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      body: data ? JSON.stringify(data) : undefined
    })
  }

  /**
   * Make a DELETE request to the specified endpoint.
   * 
   * @param url - The endpoint URL
   * @param options - Optional fetch configuration
   * @returns Promise resolving to parsed JSON response
   */
  async delete<T>(url: string, options: RequestInit = {}): Promise<T> {
    return this.request<T>(url, {
      ...options,
      method: 'DELETE'
    })
  }

  /**
   * Make a raw HTTP request with comprehensive error handling.
   * 
   * @param url - The endpoint URL
   * @param options - Fetch configuration options
   * @returns Promise resolving to parsed JSON response
   */
  private async request<T>(url: string, options: RequestInit): Promise<T> {
    const fullUrl = `${this.baseURL}${url}`
    
    try {
      const response = await fetch(fullUrl, options)
      
      if (!response.ok) {
        const error = new Error(`HTTP ${response.status}: ${response.statusText}`) as ApiError
        error.status = response.status
        
        // Try to parse error response body
        try {
          error.response = await response.json()
        } catch {
          // Response body is not JSON, keep default error message
        }
        
        throw error
      }
      
      // Handle empty responses
      const contentType = response.headers.get('content-type')
      if (!contentType || !contentType.includes('application/json')) {
        return {} as T
      }

      return (await response.json()) as T
    } catch (error) {
      if (error instanceof TypeError && error.message.includes('fetch')) {
        // Network error
        const networkError = new Error('Network error: Unable to connect to server') as ApiError
        networkError.status = 0
        throw networkError
      }
      
      throw error
    }
  }

  /**
   * Make a streaming POST request that returns the response for manual processing.
   * Used for chat streaming endpoints that return Server-Sent Events.
   * 
   * @param url - The endpoint URL
   * @param data - Request payload to be JSON serialized
   * @param options - Optional fetch configuration
   * @returns Promise resolving to Response object for stream processing
   */
  async postStream(url: string, data?: any, options: RequestInit = {}): Promise<Response> {
    const fullUrl = `${this.baseURL}${url}`
    
    const response = await fetch(fullUrl, {
      ...options,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      body: data ? JSON.stringify(data) : undefined
    })
    
    if (!response.ok) {
      const error = new Error(`HTTP ${response.status}: ${response.statusText}`) as ApiError
      error.status = response.status
      
      try {
        error.response = await response.json()
      } catch {
        // Response body is not JSON
      }
      
      throw error
    }
    
    return response
  }
}

// Create a default HTTP client instance
export const apiClient = new HttpClient()