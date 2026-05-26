import sqlite3
from app.models.db import get_connection
from app.models.admin_user import AdminUserRepository

class UserRepository:
	@staticmethod
	def get_user_by_username(username: str):
		return AdminUserRepository.get_user_by_username(username)

	@staticmethod
	def get_user_by_id(user_id: int):
		return AdminUserRepository.get_user_by_id(user_id)

	@staticmethod
	def verify_user(username: str, password: str) -> bool:
		return AdminUserRepository.verify_user(username, password)

	@staticmethod
	def get_user_roles(user_id: int) -> list:
		with get_connection() as conn:
			rows = conn.execute(
				"""SELECT DISTINCT r.id, r.role_name, r.role_code FROM roles r
				   INNER JOIN user_roles ur ON r.id = ur.role_id
				   WHERE ur.user_id=?""",
				(user_id,)
			).fetchall()
		return [dict(r) for r in rows]

	@staticmethod
	def has_role_code(user_id: int, role_code: str) -> bool:
		role_code = (role_code or "").strip()
		if not role_code:
			return False
		with get_connection() as conn:
			row = conn.execute(
				"""SELECT 1 FROM user_roles ur
				   INNER JOIN roles r ON ur.role_id = r.id
				   WHERE ur.user_id=? AND r.role_code=? LIMIT 1""",
				(user_id, role_code)
			).fetchone()
		return bool(row)

	@staticmethod
	def assign_role_by_code(user_id: int, role_code: str) -> bool:
		role_code = (role_code or "").strip()
		if not role_code:
			return False
		with get_connection() as conn:
			role_row = conn.execute("SELECT id FROM roles WHERE role_code=?", (role_code,)).fetchone()
			if not role_row:
				return False
			role_id = role_row[0]
			try:
				conn.execute(
					"INSERT OR IGNORE INTO user_roles(user_id, role_id) VALUES(?, ?)",
					(user_id, role_id)
				)
				return True
			except sqlite3.IntegrityError:
				return False

	@staticmethod
	def create_normal_user(username: str, password: str, real_name: str = "", email: str = "", phone: str = "") -> int:
		user_id = AdminUserRepository.create_user(username, password, real_name, email, phone)
		if not user_id:
			return 0
		UserRepository.assign_role_by_code(user_id, "normal_user")
		return user_id
