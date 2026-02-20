# Authentication System - Quick Guide

## Overview
The authentication system uses **JWT (JSON Web Tokens)** to securely manage user login and access control. Here's what was implemented:

## What is JWT (Simple Explanation)?
- A JWT is like a **digital ID card** that proves you're logged in
- After login, you receive a token that you send with every request
- The server verifies the token to check if you're allowed to access something
- It contains information about who you are and what you can do

## How to Use

### 1. **Registering a New User**

**Endpoint:** `POST /register`

**Request Body:**
```json
{
    "username": "john_doe",
    "password": "secure_password123",
    "role": "student",
    "student_id": "ekc23cs001"
}
```

**Response:**
```json
{
    "message": "User registered successfully",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
        "id": 1,
        "username": "john_doe",
        "role": "student",
        "student_id": "ekc23cs001"
    }
}
```

### 2. **Logging In**

**Endpoint:** `POST /login`

**Request Body:**
```json
{
    "id": "john_doe",
    "password": "secure_password123",
    "role": "student"
}
```

**Response:**
```json
{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user": {
        "id": 1,
        "username": "john_doe",
        "role": "student",
        "student_id": "ekc23cs001"
    }
}
```

### 3. **Using the Token in Requests**

After login, include the token in the Authorization header for protected endpoints:

```javascript
const token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...";

fetch('http://127.0.0.1:5000/mark_attendance', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`  // Add the token here!
    },
    body: JSON.stringify({
        "student_id": "ekc23cs001"
    })
});
```

### 4. **Verifying Token Validity**

**Endpoint:** `GET /verify-token`

**Headers:**
```
Authorization: Bearer <your_token>
```

**Response:**
```json
{
    "valid": true,
    "user_id": 1,
    "role": "student"
}
```

## Protected Endpoints

These endpoints now require authentication (valid JWT token):

1. **`POST /mark_attendance`** - Mark student attendance
2. **`POST /students`** - Add new student
3. **`POST /students/toggle_leave`** - Toggle leave status

## Public Endpoints (No Login Required)

- `GET /` - Home page
- `GET /students` - Get all students
- `GET /attendance` - Get attendance records
- `GET /students/count` - Count students
- `GET /health` - Health check
- `POST /login` - User login
- `POST /register` - User registration

## Password Security

⚠️ **Important:**
- Passwords are **hashed** before storing in database (cannot be recovered)
- Never store plain passwords
- Use `pbkdf2:sha256` algorithm for hashing

## Frontend Integration Steps

### Step 1: Store Token After Login
```javascript
// After successful login
const response = await fetch('http://127.0.0.1:5000/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, password, role })
});

const data = await response.json();
localStorage.setItem('authTokenok now i have made many changes since we last chat. because you were unavailable because of the limit. so now i want you to make the authentication in backend.', data.token);  // Save token
localStorage.setItem('user', JSON.stringify(data.user));  // Save user info
```

### Step 2: Use Token in Protected Requests
```javascript
// Get token from storage
const token = localStorage.getItem('authToken');

// Add to every request that needs auth
const headers = {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
};
```

### Step 3: Handle Token Expiry
```javascript
// When you get 401 error, token is expired
if (response.status === 401) {
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    window.location.href = 'login.html';  // Redirect to login
}
```

## Error Responses

| Status Code | Error | Meaning |
|-------------|-------|---------|
| 400 | "Missing username or password" | Incomplete login credentials |
| 401 | "Invalid username or password" | Wrong credentials |
| 403 | "Insufficient permissions" | User role doesn't match |
| 401 | Expired/Invalid token | Token is no longer valid |
| 500 | "Login failed" | Server error |

## Database Changes

A new `users` table was created with:
- `username` - Login username (unique)
- `password_hash` - Encrypted password
- `role` - User type (admin, student, driver)
- `student_id` - Links to student (if applicable)

## Security Tips

1. ✅ Change `JWT_SECRET_KEY` in production to something secure
2. ✅ Always use HTTPS in production (not HTTP)
3. ✅ Never log passwords
4. ✅ Store token in localStorage on frontend
5. ✅ Clear token on logout
6. ✅ Validate role on sensitive operations

## Testing the Authentication

### Create a Test User
```bash
curl -X POST http://127.0.0.1:5000/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "test123",
    "role": "student",
    "student_id": "ekc23cs001"
  }'
```

### Login
```bash
curl -X POST http://127.0.0.1:5000/login \
  -H "Content-Type: application/json" \
  -d '{
    "id": "testuser",
    "password": "test123",
    "role": "student"
  }'
```

### Use Token in Request
```bash
curl -X POST http://127.0.0.1:5000/mark_attendance \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN_FROM_LOGIN>" \
  -d '{"student_id": "ekc23cs001"}'
```

---

**Authentication is now ready!** Next steps: Update your frontend to send tokens with requests.
