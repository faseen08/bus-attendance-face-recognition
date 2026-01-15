#!/usr/bin/env python3
import os
import sqlite3

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'database', 'bus.db')
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'students')

def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    for name in sorted(os.listdir(DATA_DIR)):
        path = os.path.join(DATA_DIR, name)
        if not os.path.isdir(path):
            continue
        student_id = name
        # try to find a photo file
        photo = None
        for fname in os.listdir(path):
            if fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                photo = os.path.join('data', 'students', name, fname)
                break

        # insert if not exists
        c.execute('SELECT id FROM students WHERE student_id = ?', (student_id,))
        if c.fetchone():
            print(f"Skipping existing {student_id}")
            continue

        c.execute(
            'INSERT INTO students (student_id, name, photo_path) VALUES (?, ?, ?)',
            (student_id, student_id, photo)
        )
        print(f"Inserted {student_id}")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    main()
