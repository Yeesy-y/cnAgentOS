"""
更新数据库：添加 employee_messages 表
"""
import sqlite3
import os

# 获取项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_path = os.path.join(project_root, 'database', 'app.db')

print(f"数据库路径: {db_path}")

# 确保数据库目录存在
os.makedirs(os.path.dirname(db_path), exist_ok=True)

# 连接数据库
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # 检查表是否已存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='employee_messages'")
    table_exists = cursor.fetchone()
    
    if table_exists:
        print("employee_messages 表已存在，跳过创建")
    else:
        # 创建表
        print("正在创建 employee_messages 表...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employee_messages(
                id integer PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                employee_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                is_user INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(employee_id) REFERENCES digital_employees(id)
            )
        """)
        print("employee_messages 表创建成功")
        
        conn.commit()
        print("数据库更新成功！")
        
except Exception as e:
    print(f"更新数据库时出错: {e}")
    conn.rollback()
finally:
    conn.close()
    print("数据库连接已关闭")
