// API Service Layer for Backend Integration
// Replace BASE_URL with your actual backend endpoint

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000/api'

// Generic fetch wrapper with error handling
async function apiRequest<T>(endpoint: string, options?: RequestInit): Promise<T> {
  try {
    const response = await fetch(`${BASE_URL}${endpoint}`, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    })

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`)
    }

    return await response.json()
  } catch (error) {
    console.error(`API Request failed for ${endpoint}:`, error)
    throw error
  }
}

export { apiRequest, BASE_URL }