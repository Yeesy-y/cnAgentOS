from app.models.db import get_connection

conn = get_connection()
try:
    conn.execute("DELETE FROM user_roles")
    conn.execute("DELETE FROM users WHERE id > 1")
    conn.execute("DELETE FROM sqlite_sequence WHERE name='users'")
    conn.commit()
    print("OK")
except Exception as e:
    print("ERROR:", e)
    conn.rollback()
finally:
    conn.close()
