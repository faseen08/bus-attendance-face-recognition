/**
 * API Utility Module
 * 
 * This module handles all API communication with the backend.
 * It automatically includes the JWT token with every request.
 * 
 * Think of it as a "smart messenger" that remembers your token
 * and sends it with every message to the server.
 */

const API_BASE = "http://127.0.0.1:5000";
const TOKEN_KEY = "authToken"; // Key name for storing token in browser storage

/**
 * Get the stored authentication token from browser storage
 * 
 * @returns {string|null} The JWT token or null if not logged in
 */
function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Store authentication token in browser storage
 * 
 * @param {string} token - JWT token to store
 */
function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

/**
 * Remove authentication token (logout)
 */
function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * Check if user is currently logged in
 * 
 * @returns {boolean} True if token exists
 */
function isLoggedIn() {
  return !!getToken();
}

/**
 * Make an authenticated API call
 * 
 * This function:
 * 1. Takes your request details (method, body, etc.)
 * 2. Automatically adds the JWT token to the request headers
 * 3. Sends the request to the backend
 * 4. Handles common errors:
 *    - 401 (Unauthorized): Token expired/invalid → Redirect to login
 *    - Other errors: Returns error response
 * 
 * Usage Examples:
 * 
 * // GET request (retrieve data)
 * const students = await apiCall('/students');
 * 
 * // POST request (send data)
 * const response = await apiCall('/mark_attendance', {
 *   method: 'POST',
 *   body: { student_id: 'ekc23cs001' }
 * });
 * 
 * @param {string} endpoint - API path (e.g., '/students', '/mark_attendance')
 * @param {object} options - Request options
 * @param {string} options.method - HTTP method (GET, POST, PUT, DELETE)
 * @param {object} options.body - Data to send (automatically converted to JSON)
 * @param {object} options.headers - Custom headers (optional)
 * 
 * @returns {Promise<Response>} Response from the server
 */
async function apiCall(endpoint, options = {}) {
  // Set default method to GET
  const method = options.method || 'GET';
  
  // Create headers object
  const headers = {
    ...options.headers
  };
  
  // Add token to headers if user is logged in
  const token = getToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  // Prepare request configuration
  const requestConfig = {
    method,
    headers
  };
  
  // Add body if provided (for POST, PUT, etc.)
  if (options.body) {
    // Check if body is FormData (for file uploads)
    if (options.body instanceof FormData) {
      // Don't set Content-Type header - browser will set it with boundary
      // Remove any existing Content-Type header
      delete headers['Content-Type'];
      requestConfig.body = options.body;
    } else {
      // Regular JSON body
      headers['Content-Type'] = 'application/json';
      requestConfig.body = JSON.stringify(options.body);
    }
  } else {
    // Set default Content-Type for non-FormData requests
    headers['Content-Type'] = 'application/json';
  }
  
  try {
    // Make the API call
    const response = await fetch(`${API_BASE}${endpoint}`, requestConfig);
    
    // Do not auto-redirect here. Let callers decide how to handle 401 responses.
    // Return the response so the caller can inspect status/code.
    if (response.status === 401) {
      return response;
    }
    
    // Handle other error status codes
    if (!response.ok) {
      const errorData = await response.clone().json().catch(() => ({}));
      console.error(`API Error (${response.status}):`, errorData);

      // Common stale-token case after JWT identity format changes
      if (response.status === 422 && (errorData.msg || '').toLowerCase().includes('subject must be a string')) {
        clearToken();
        window.location.href = 'index.html';
      }

      return response; // Still return response so caller can handle it
    }
    
    return response;
    
  } catch (error) {
    console.error("Network error:", error);
    throw error; // Re-throw so caller can handle it
  }
}

/**
 * Make an API call and parse JSON response
 * 
 * This is a convenience function that:
 * 1. Calls apiCall()
 * 2. Automatically converts response to JSON
 * 
 * If you need the raw response, use apiCall() instead.
 * 
 * @param {string} endpoint - API path
 * @param {object} options - Request options (same as apiCall)
 * 
 * @returns {Promise<object>} Parsed JSON response
 */
async function apiCallJSON(endpoint, options = {}) {
  const response = await apiCall(endpoint, options);
  
  if (!response) return null;

  // If token is invalid/expired, force logout and redirect to login
  if (response.status === 401) {
    clearToken();
    window.location.href = 'index.html';
    return null;
  }
  
  try {
    return await response.json();
  } catch (error) {
    console.error("Failed to parse response as JSON:", error);
    return null;
  }
}

/**
 * Login function
 * 
 * Sends credentials to backend and stores token if successful
 * 
 * @param {string} username - Username or student ID
 * @param {string} password - Password
 * @param {string} role - User role ('student' or 'admin')
 * 
 * @returns {Promise<object>} User info and token or error
 */
async function login(username, password, role) {
  const response = await apiCall('/login', {
    method: 'POST',
    body: {
      id: username,
      password: password,
      role: role
    }
  });
  
  if (!response.ok) {
    const error = await response.json();
    return { error: error.error || 'Login failed' };
  }
  
  const data = await response.json();
  
  // Store token if login successful
  if (data.token) {
    setToken(data.token);
  }
  
  return data;
}

/**
 * Logout function
 * 
 * Clears token from storage
 */
function logout() {
  clearToken();
  window.location.href = 'index.html';
}
