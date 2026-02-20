"""
Initialize Admin and Test User Accounts

This script creates initial admin and student accounts in the database.
Run this ONCE at the beginning to set up your authentication system.

Usage:
    python init_users.py

This will create:
- Admin account: username='admin', password='admin123'
- Student accounts with passwords for testing
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(__file__))

from database.db import get_connection, init_db
from backend.auth import create_user, hash_password

def init_users():
    """Initialize admin and test student accounts"""
    
    try:
        # Initialize database schema first
        print("📁 Initializing database schema...")
        init_db()
        print("✅ Database schema ready")
        
        # Create admin user
        print("\n👨‍💼 Creating admin account...")
        admin_result = create_user(
            username='admin',
            password='admin123',
            role='admin',
            student_id=None
        )
        
        if admin_result['success']:
            print(f"✅ Admin created: username='admin', password='admin123'")
        else:
            if 'unique constraint failed' in admin_result['error'].lower():
                print("⚠️  Admin account already exists (that's fine!)")
            else:
                print(f"❌ Error creating admin: {admin_result['error']}")
        
        # Create test student accounts
        print("\n👨‍🎓 Creating test student accounts...")
        
        test_students = [
            {'student_id': 'ekc23cs001', 'password': 'pass123'},
            {'student_id': 'ekc23cs002', 'password': 'pass123'},
            {'student_id': 'ekc23cs003', 'password': 'pass123'},
            {'student_id': 'ekc23cs004', 'password': 'pass123'},
            {'student_id': 'ekc23cs005', 'password': 'pass123'},
        ]
        
        for student in test_students:
            student_result = create_user(
                username=student['student_id'],
                password=student['password'],
                role='student',
                student_id=student['student_id']
            )
            
            if student_result['success']:
                print(f"✅ Student created: {student['student_id']}")
                # Also ensure the student exists in the students table
                try:
                    conn = get_connection()
                    exists = conn.execute(
                        "SELECT id FROM students WHERE student_id = ?",
                        (student['student_id'],)
                    ).fetchone()
                    if not exists:
                        conn.execute(
                            "INSERT INTO students (student_id, name, photo_path) VALUES (?, ?, ?)",
                            (student['student_id'], student['student_id'], None)
                        )
                        conn.commit()
                        print(f"   ↳ Added {student['student_id']} to students table")
                    conn.close()
                except Exception as e:
                    print(f"   ⚠️ Failed to insert into students table: {e}")
            else:
                if 'unique constraint failed' in student_result['error'].lower():
                    print(f"⚠️  Student {student['student_id']} already exists (skipping)")
                    # Even if the user exists, ensure the student record exists in students table
                    try:
                        conn = get_connection()
                        exists = conn.execute(
                            "SELECT id FROM students WHERE student_id = ?",
                            (student['student_id'],)
                        ).fetchone()
                        if not exists:
                            conn.execute(
                                "INSERT INTO students (student_id, name, photo_path) VALUES (?, ?, ?)",
                                (student['student_id'], student['student_id'], None)
                            )
                            conn.commit()
                            print(f"   ↳ Added {student['student_id']} to students table")
                        conn.close()
                    except Exception as e:
                        print(f"   ⚠️ Failed to insert into students table: {e}")
                else:
                    print(f"❌ Error creating {student['student_id']}: {student_result['error']}")
        
        print("\n" + "="*50)
        print("✅ INITIALIZATION COMPLETE!")
        print("="*50)
        print("\n📝 Login Credentials:")
        print("\nADMIN:")
        print("  Username: admin")
        print("  Password: admin123")
        print("  Role: admin")
        print("\nTEST STUDENTS:")
        print("  Username: ekc23cs001 - ekc23cs005")
        print("  Password: pass123 (same for all)")
        print("  Role: student")
        print("\n💡 You can now login to the dashboard!")
        print("="*50)
        
    except Exception as e:
        print(f"❌ Error during initialization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    init_users()
