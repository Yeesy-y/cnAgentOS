import os
import sqlite3
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))
from app.models.db import get_connection, init_db

conn = get_connection()
try:
    conn.execute("BEGIN TRANSACTION")
    
    # 1. 备份现有 admin 用户数据
    cursor = conn.execute("SELECT username, password_hash, salt, real_name, status FROM users WHERE id=1")
    admin_row = cursor.fetchone()
    
    # 2. 清空用户表
    conn.execute("DELETE FROM users")
    conn.execute("DELETE FROM user_roles")
    
    # 3. 重置自增ID
    conn.execute("DELETE FROM sqlite_sequence WHERE name='users'")
    
    # 4. 重新插入 admin 用户
    if admin_row:
        conn.execute("""
            INSERT INTO users(username, password_hash, salt, real_name, status, create_at, update_at)
            VALUES(?, ?, ?, ?, 1, datetime('now'), datetime('now'))
        """, admin_row)
        
        # 重新获取新插入的ID
        new_admin_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
        # 重新分配角色
        cursor = conn.execute("SELECT id FROM roles WHERE role_code='super_admin'")
        role_row = cursor.fetchone()
        if role_row:
            conn.execute(
                "INSERT INTO user_roles(user_id, role_id) VALUES(?,?)",
                (new_admin_id, role_row[0])
            )
    
    conn.commit()
    print("✅ 重置用户表成功！")
    print("- admin 用户ID已重置为 1")
    
    print("- 自增ID已重置")
    
except Exception as e:
    conn.rollback()
    print(f"❌ 错误:", e)
finally:
    conn.close()
