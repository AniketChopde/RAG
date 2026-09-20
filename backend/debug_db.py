#!/usr/bin/env python3
"""
Debug script to check database contents
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

def check_database():
    print("🔍 Checking Database Contents")
    print("=" * 40)

    if not os.path.exists(DB_PATH):
        print("❌ Database file not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Check users table
    print("\n1. Users Table:")
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    print(f"   Total users: {user_count}")

    if user_count > 0:
        cur.execute("SELECT id, username, role, created_at FROM users")
        users = cur.fetchall()
        for user in users:
            print(f"   - {user['username']} ({user['role']}) - ID: {user['id']}")
    else:
        print("   No users found!")

    # Check uploaded_documents table
    print("\n2. Uploaded Documents Table:")
    cur.execute("SELECT COUNT(*) FROM uploaded_documents")
    doc_count = cur.fetchone()[0]
    print(f"   Total uploaded documents: {doc_count}")

    if doc_count > 0:
        cur.execute("SELECT ud.id, ud.name, u.username FROM uploaded_documents ud LEFT JOIN users u ON ud.user_id = u.id")
        docs = cur.fetchall()
        for doc in docs:
            username = doc['username'] or 'Unknown'
            print(f"   - {doc['name']} (uploaded by: {username})")

    # Check conversations table
    print("\n3. Conversations Table:")
    cur.execute("SELECT COUNT(*) FROM conversations")
    conv_count = cur.fetchone()[0]
    print(f"   Total conversations: {conv_count}")

    conn.close()

    print("\n✅ Database check completed!")

if __name__ == "__main__":
    check_database()
