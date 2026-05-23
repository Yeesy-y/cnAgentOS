from app.models.db import get_connection

conn = get_connection()
try:
    cursor = conn.execute("SELECT id FROM users WHERE username='admin'")
    admin_user = cursor.fetchone()
    
    if admin_user:
        admin_user_id = admin_user[0]
        
        cursor = conn.execute("SELECT id FROM roles WHERE role_code='super_admin'")
        super_admin_role = cursor.fetchone()
        
        if super_admin_role:
            super_admin_role_id = super_admin_role[0]
            
            cursor = conn.execute(
                "SELECT COUNT(*) FROM user_roles WHERE user_id=? AND role_id=?",
                (admin_user_id, super_admin_role_id)
            )
            if cursor.fetchone()[0] == 0:
                conn.execute(
                    "INSERT INTO user_roles(user_id, role_id) VALUES(?,?)",
                    (admin_user_id, super_admin_role_id)
                )
                print("Admin user role assigned successfully")
            else:
                print("Admin user already has super admin role")
    
    conn.commit()
    print("OK")
except Exception as e:
    print("ERROR:", e)
    conn.rollback()
finally:
    conn.close()
