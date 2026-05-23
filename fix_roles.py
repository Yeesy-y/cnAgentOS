from app.models.db import get_connection

conn = get_connection()
try:
    conn.execute("DELETE FROM user_roles WHERE id = 35")
    conn.execute("UPDATE roles SET role_name = 'admin' WHERE role_code = 'super_admin'")
    conn.commit()
    print("OK")
except Exception as e:
    print("ERROR:", e)
    conn.rollback()
finally:
    conn.close()
