from app.models.db import get_connection

conn = get_connection()
try:
    cursor = conn.execute("SELECT id FROM users WHERE username='admin'")
    admin_user = cursor.fetchone()
    if admin_user:
        admin_id = admin_user['id']
        
        cursor = conn.execute(
            "SELECT id, role_id FROM user_roles WHERE user_id=? ORDER BY id", 
            (admin_id,)
        )
        rows = cursor.fetchall()
        
        seen_role_ids = set()
        to_delete_ids = []
        
        for row in rows:
            role_id = row['role_id']
            if role_id in seen_role_ids:
                to_delete_ids.append(row['id'])
            else:
                seen_role_ids.add(role_id)
        
        if to_delete_ids:
            for rid in to_delete_ids:
                conn.execute("DELETE FROM user_roles WHERE id=?", (rid,))
            print(f"Deleted {len(to_delete_ids)} duplicate role records for admin user")
        else:
            print("No duplicate roles found")
    
    conn.commit()
except Exception as e:
    print("ERROR:", e)
    conn.rollback()
finally:
    conn.close()

print("OK")
