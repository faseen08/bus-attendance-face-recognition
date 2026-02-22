"""
Authentication utilities for the bus attendance system.
Handles password hashing, verification, and JWT token management.
"""

from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from functools import wraps
from database.db import get_connection
from flask import jsonify

# ============================================================================
# PASSWORD MANAGEMENT
# ============================================================================

def hash_password(password):
    """
    Convert a plain text password into a secure hash.
    This makes it safe to store passwords in the database.
    
    Args:
        password (str): Plain text password
        
    Returns:
        str: Hashed password
    """
    return generate_password_hash(password, method='pbkdf2:sha256')


def verify_password(password, password_hash):
    """
    Check if a plain text password matches a stored password hash.
    
    Args:
        password (str): Plain text password to check
        password_hash (str): Stored hash from database
        
    Returns:
        bool: True if password matches, False otherwise
    """
    return check_password_hash(password_hash, password)


# ============================================================================
# USER MANAGEMENT
# ============================================================================

def create_user(username, password, role='student', student_id=None):
    """
    Create a new user account.
    
    Args:
        username (str): Unique username
        password (str): Plain text password (will be hashed)
        role (str): User role - 'student', 'admin', or 'driver'
        student_id (str): Student ID if role is 'student'
        
    Returns:
        dict: {"success": True, "message": "..."} or error dict
    """
    try:
        # Hash the password before storing
        password_hash = hash_password(password)
        
        conn = get_connection()
        conn.execute(
            """INSERT INTO users (username, password_hash, role, student_id) 
               VALUES (?, ?, ?, ?)""",
            (username, password_hash, role, student_id)
        )
        conn.commit()
        conn.close()
        
        return {"success": True, "message": "User created successfully"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


def authenticate_user(username, password):
    """
    Verify user credentials and return user info if valid.
    
    Args:
        username (str): Username to authenticate
        password (str): Password to verify
        
    Returns:
        dict: User info (id, username, role, student_id) if successful,
              None if authentication fails
    """
    try:
        conn = get_connection()
        user = conn.execute(
            "SELECT id, username, password_hash, role, student_id FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        conn.close()
        
        # User doesn't exist
        if not user:
            return None
        
        # Verify password
        if verify_password(password, user['password_hash']):
            # Password is correct - return user info (without hash)
            return {
                "id": user['id'],
                "username": user['username'],
                "role": user['role'],
                "student_id": user['student_id']
            }
        else:
            # Password is wrong
            return None
    
    except Exception as e:
        return None


def get_user_by_id(user_id):
    """
    Get user information by user ID.
    
    Args:
        user_id (int): User ID
        
    Returns:
        dict: User info or None if not found
    """
    try:
        conn = get_connection()
        user = conn.execute(
            "SELECT id, username, role, student_id FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        conn.close()
        
        return dict(user) if user else None
    except Exception:
        return None


# ============================================================================
# JWT TOKEN MANAGEMENT
# ============================================================================

def generate_token(user_id, username, role):
    """
    Generate a JWT token for authenticated user.
    This token is used for subsequent requests to prove authentication.
    
    Args:
        user_id (int): User ID
        username (str): Username
        role (str): User role
        
    Returns:
        str: JWT token
    """
    return create_access_token(
        identity=str(user_id),
        additional_claims={
            "username": username,
            "role": role
        }
    )


# ============================================================================
# DECORATORS FOR PROTECTED ENDPOINTS
# ============================================================================

def require_auth(fn):
    """
    Decorator to require JWT authentication on an endpoint.
    Automatically checks for valid token and extracts user info.
    
    Usage:
        @app.route('/protected', methods=['GET'])
        @require_auth
        def protected_route():
            user_id = get_jwt_identity()
            return jsonify({"user": user_id})
    """
    @wraps(fn)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        return fn(*args, **kwargs)
    return decorated_function


def require_role(role):
    """
    Decorator to require specific role for an endpoint.
    
    Usage:
        @app.route('/admin', methods=['GET'])
        @require_auth
        @require_role('admin')
        def admin_endpoint():
            return jsonify({"message": "Admin only"})
    """
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            from flask_jwt_extended import get_jwt
            claims = get_jwt()
            
            if claims.get('role') != role:
                return jsonify({"error": "Insufficient permissions"}), 403
            
            return fn(*args, **kwargs)
        return decorated_function
    return decorator
