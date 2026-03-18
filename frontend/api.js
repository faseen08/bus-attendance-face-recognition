/**
 * API Utility Module
 * 
 * This module handles all API communication with the backend.
 * It automatically includes the JWT token with every request.
 * 
 * Think of it as a "smart messenger" that remembers your token
 * and sends it with every message to the server.
 */

const DEFAULT_API_BASE = "http://127.0.0.1:5000";
const API_BASE_KEY = "apiBaseUrl";

function _getApiBaseFromQuery() {
  try {
    const params = new URLSearchParams(window.location.search);
    const api = params.get('api');
    return api ? api.trim() : null;
  } catch {
    return null;
  }
}

function _getApiBase() {
  const fromQuery = _getApiBaseFromQuery();
  if (fromQuery) {
    localStorage.setItem(API_BASE_KEY, fromQuery);
    return fromQuery;
  }
  const stored = localStorage.getItem(API_BASE_KEY);
  if (stored) return stored;
  // If frontend is served by backend under /frontend, use same origin by default.
  if (window.location && window.location.pathname.startsWith('/frontend/')) {
    return window.location.origin;
  }
  // If served over HTTPS (e.g., ngrok), use same origin by default.
  if (window.location && window.location.protocol === 'https:') {
    return window.location.origin;
  }
  return DEFAULT_API_BASE;
}

const API_BASE = _getApiBase();
const TOKEN_KEY = "authToken"; // Legacy key (fallback)
const ROLE_TOKEN_KEYS = {
  student: "authToken_student",
  driver: "authToken_driver",
  admin: "authToken_admin"
};

/**
 * Get the stored authentication token from browser storage
 * 
 * @returns {string|null} The JWT token or null if not logged in
 */
function _currentRole() {
  return window.APP_ROLE || null;
}

function _roleKey(role) {
  return ROLE_TOKEN_KEYS[role] || TOKEN_KEY;
}

function getToken() {
  const role = _currentRole();
  if (role) {
    const roleToken = localStorage.getItem(_roleKey(role));
    if (roleToken) return roleToken;
  }
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Store authentication token in browser storage
 * 
 * @param {string} token - JWT token to store
 */
function setToken(token, role) {
  const targetRole = role || _currentRole();
  if (targetRole) {
    localStorage.setItem(_roleKey(targetRole), token);
    return;
  }
  localStorage.setItem(TOKEN_KEY, token);
}

/**
 * Remove authentication token (logout)
 */
function clearToken(role) {
  const targetRole = role || _currentRole();
  if (targetRole) {
    localStorage.removeItem(_roleKey(targetRole));
    return;
  }
  localStorage.removeItem(TOKEN_KEY);
}

function clearAllTokens() {
  Object.values(ROLE_TOKEN_KEYS).forEach((key) => localStorage.removeItem(key));
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
    // For GET/HEAD, avoid forcing content-type headers.
    // This reduces unnecessary preflight requests in browsers.
    if (method !== 'GET' && method !== 'HEAD') {
      headers['Content-Type'] = 'application/json';
    }
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
        clearAllTokens();
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
    clearAllTokens();
    window.location.href = 'index.html';
    return null;
  }
  
  const payload = await response.clone().json().catch(() => null);
  if (!response.ok) {
    if (payload && typeof payload === 'object') {
      return payload;
    }
    return { error: `Request failed with status ${response.status}` };
  }
  return payload;
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
    setToken(data.token, role);
  }
  
  return data;
}

/**
 * Logout function
 * 
 * Clears token from storage
 */
function logout() {
  clearAllTokens();
  window.location.href = 'index.html';
}
