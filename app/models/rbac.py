from app.models.db import get_connection

class PermissionRepository:
	@staticmethod
	def list_all():
		with get_connection() as conn:
			rows = conn.execute("SELECT * FROM permissions ORDER BY sort_order, id").fetchall()
		return [dict(r) for r in rows]

	@staticmethod
	def list_tree():
		perms = PermissionRepository.list_all()
		tree = []
		id_map = {}
		for p in perms:
			p["children"] = []
			id_map[p["id"]] = p
		for p in perms:
			if p["parent_id"] == 0:
				tree.append(p)
			else:
				if p["parent_id"] in id_map:
					id_map[p["parent_id"]]["children"].append(p)
		return tree

	@staticmethod
	def get_by_id(perm_id):
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM permissions WHERE id=?", (perm_id,)).fetchone()
		return dict(row) if row else None

	@staticmethod
	def create(perm_name, perm_code, parent_id=0, menu_url="", sort_order=0):
		with get_connection() as conn:
			cursor = conn.execute(
				"INSERT INTO permissions(perm_name, perm_code, parent_id, menu_url, sort_order) VALUES(?,?,?,?,?)",
				(perm_name, perm_code, parent_id, menu_url, sort_order)
			)
			conn.commit()
			return cursor.lastrowid

	@staticmethod
	def update(perm_id, perm_name=None, perm_code=None, parent_id=None, menu_url=None, sort_order=None):
		with get_connection() as conn:
			sets = []
			params = []
			if perm_name is not None:
				sets.append("perm_name=?")
				params.append(perm_name)
			if perm_code is not None:
				sets.append("perm_code=?")
				params.append(perm_code)
			if parent_id is not None:
				sets.append("parent_id=?")
				params.append(parent_id)
			if menu_url is not None:
				sets.append("menu_url=?")
				params.append(menu_url)
			if sort_order is not None:
				sets.append("sort_order=?")
				params.append(sort_order)
			if not sets:
				return
			params.append(perm_id)
			conn.execute(f"UPDATE permissions SET {','.join(sets)} WHERE id=?", params)
			conn.commit()

	@staticmethod
	def delete(perm_id):
		with get_connection() as conn:
			conn.execute("DELETE FROM role_permissions WHERE permission_id=?", (perm_id,))
			conn.execute("DELETE FROM permissions WHERE id=?", (perm_id,))
			conn.commit()


class RoleRepository:
	@staticmethod
	def list_all():
		with get_connection() as conn:
			rows = conn.execute("SELECT * FROM roles ORDER BY id").fetchall()
		return [dict(r) for r in rows]

	@staticmethod
	def get_by_id(role_id):
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM roles WHERE id=?", (role_id,)).fetchone()
		return dict(row) if row else None

	@staticmethod
	def create(role_name, role_code, description=""):
		with get_connection() as conn:
			cursor = conn.execute(
				"INSERT INTO roles(role_name, role_code, description) VALUES(?,?,?)",
				(role_name, role_code, description)
			)
			conn.commit()
			return cursor.lastrowid

	@staticmethod
	def update(role_id, role_name=None, role_code=None, description=None, status=None):
		with get_connection() as conn:
			sets = []
			params = []
			if role_name is not None:
				sets.append("role_name=?")
				params.append(role_name)
			if role_code is not None:
				sets.append("role_code=?")
				params.append(role_code)
			if description is not None:
				sets.append("description=?")
				params.append(description)
			if status is not None:
				sets.append("status=?")
				params.append(status)
			if not sets:
				return
			params.append(role_id)
			conn.execute(f"UPDATE roles SET {','.join(sets)} WHERE id=?", params)
			conn.commit()

	@staticmethod
	def delete(role_id):
		with get_connection() as conn:
			conn.execute("DELETE FROM user_roles WHERE role_id=?", (role_id,))
			conn.execute("DELETE FROM role_permissions WHERE role_id=?", (role_id,))
			conn.execute("DELETE FROM roles WHERE id=?", (role_id,))
			conn.commit()

	@staticmethod
	def assign_permissions(role_id, perm_ids):
		with get_connection() as conn:
			conn.execute("DELETE FROM role_permissions WHERE role_id=?", (role_id,))
			if perm_ids:
				conn.executemany(
					"INSERT INTO role_permissions(role_id, permission_id) VALUES(?,?)",
					[(role_id, pid) for pid in perm_ids]
				)
			conn.commit()

	@staticmethod
	def get_permission_ids(role_id):
		with get_connection() as conn:
			rows = conn.execute("SELECT permission_id FROM role_permissions WHERE role_id=?", (role_id,)).fetchall()
		return [r[0] for r in rows]
