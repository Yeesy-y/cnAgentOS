#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
from app.models.db import get_connection
from app.models.admin_user import AdminUserRepository

print("==== 数据库调试 ====")
conn = get_connection()

try:
    print("\n1. 检查 users 表结构：")
    cursor = conn.execute("PRAGMA table_info(users)")
    for row in cursor.fetchall():
        print(f"  {row}")

    print("\n2. 检查 users 表数据：")
    rows = conn.execute("SELECT * FROM users").fetchall()
    for r in rows:
        print(f"  {dict(r)}")

    print("\n3. 测试 AdminUserRepository.list_users()：")
    result = AdminUserRepository.list_users(1, 20)
    print(f"  total: {result['total']}")
    print(f"  data: {result['data']}")

    print("\n==== 调试完成 ====")

finally:
    conn.close()
