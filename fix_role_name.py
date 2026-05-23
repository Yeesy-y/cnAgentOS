from app.models.db import get_connection

conn = get_connection()
try:
    conn.execute("UPDATE roles SET role_name = '超级管理员' WHERE role_code = 'super_admin'")
    conn.commit()
    print("OK")
except Exception as e:
    print("ERROR:", e)
    conn.rollback()
finally:
    conn.close()
