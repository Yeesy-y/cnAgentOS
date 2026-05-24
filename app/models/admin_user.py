import hashlib
import secrets
import sqlite3

from app.models.db import get_connection

def _hash_password(password:str, salt:bytes) -> str:
	dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
	return dk.hex()

class AdminUserRepository:
	@staticmethod
	def create_user(username:str, password:str, real_name:str="", email:str="", phone:str="") -> int:
		salt = secrets.token_bytes(16)
		password_hash = _hash_password(password, salt)
		try:
			with get_connection() as conn:
				cursor = conn.execute("PRAGMA table_info(users)")
				existing_cols = {row[1] for row in cursor.fetchall()}
				cols = ["username", "password_hash", "salt"]
				vals = [username, password_hash, salt.hex()]
				if "real_name" in existing_cols:
					cols.append("real_name")
					vals.append(real_name)
				if "email" in existing_cols:
					cols.append("email")
					vals.append(email)
				if "phone" in existing_cols:
					cols.append("phone")
					vals.append(phone)
				cursor = conn.execute(
					f"INSERT INTO users({','.join(cols)}) VALUES({','.join(['?']*len(vals))})",
					tuple(vals)
				)
				return cursor.lastrowid
		except sqlite3.IntegrityError:
			return 0

	@staticmethod
	def get_user_by_id(user_id:int):
		with get_connection() as conn:
			cursor = conn.execute("PRAGMA table_info(users)")
			existing_cols = {row[1] for row in cursor.fetchall()}
			cols = ["id", "username"]
			if "real_name" in existing_cols:
				cols.append("real_name")
			if "email" in existing_cols:
				cols.append("email")
			if "phone" in existing_cols:
				cols.append("phone")
			if "status" in existing_cols:
				cols.append("status")
			if "create_at" in existing_cols:
				cols.append("create_at")
			if "update_at" in existing_cols:
				cols.append("update_at")
			row = conn.execute(
				f"SELECT {','.join(cols)} FROM users WHERE id=?",
				(user_id,)
			).fetchone()
		return row

	@staticmethod
	def get_user_by_username(username:str):
		with get_connection() as conn:
			cursor = conn.execute("PRAGMA table_info(users)")
			existing_cols = {row[1] for row in cursor.fetchall()}
			cols = ["id", "username", "password_hash", "salt"]
			if "real_name" in existing_cols:
				cols.append("real_name")
			if "email" in existing_cols:
				cols.append("email")
			if "phone" in existing_cols:
				cols.append("phone")
			if "status" in existing_cols:
				cols.append("status")
			if "create_at" in existing_cols:
				cols.append("create_at")
			if "update_at" in existing_cols:
				cols.append("update_at")
			row = conn.execute(
				f"SELECT {','.join(cols)} FROM users WHERE username=?",
				(username,)
			).fetchone()
		return row

	@staticmethod
	def verify_user(username:str, password:str) -> bool:
		row = AdminUserRepository.get_user_by_username(username)
		if not row:
			return False
		salt = bytes.fromhex(row["salt"])
		return _hash_password(password, salt) == row["password_hash"]

	@staticmethod
	def update_user(user_id:int, real_name:str=None, email:str=None, phone:str=None, password:str=None, status:int=None) -> bool:
		fields = []
		values = []
		if real_name is not None:
			fields.append("real_name=?")
			values.append(real_name)
		if email is not None:
			fields.append("email=?")
			values.append(email)
		if phone is not None:
			fields.append("phone=?")
			values.append(phone)
		if status is not None:
			fields.append("status=?")
			values.append(status)
		if password is not None:
			salt = secrets.token_bytes(16)
			password_hash = _hash_password(password, salt)
			fields.append("password_hash=?")
			fields.append("salt=?")
			values.append(password_hash)
			values.append(salt.hex())
		if not fields:
			return False
		fields.append("update_at=datetime('now')")
		values.append(user_id)
		sql = f"UPDATE users SET {','.join(fields)} WHERE id=?"
		try:
			with get_connection() as conn:
				conn.execute(sql, values)
			return True
		except sqlite3.IntegrityError:
			return False

	@staticmethod
	def delete_user(user_id:int) -> bool:
		try:
			with get_connection() as conn:
				conn.execute("DELETE FROM user_roles WHERE user_id=?", (user_id,))
				conn.execute("DELETE FROM users WHERE id=?", (user_id,))
			return True
		except sqlite3.IntegrityError:
			return False

	@staticmethod
	def delete_users(user_ids:list) -> int:
		count = 0
		with get_connection() as conn:
			for uid in user_ids:
				try:
					conn.execute("DELETE FROM user_roles WHERE user_id=?", (uid,))
					conn.execute("DELETE FROM users WHERE id=?", (uid,))
					count += 1
				except sqlite3.IntegrityError:
					pass
		return count

	@staticmethod
	def list_users(page:int=1, page_size:int=20, keyword:str="") -> dict:
		offset = (page - 1) * page_size
		with get_connection() as conn:
			cursor = conn.execute("PRAGMA table_info(users)")
			existing_cols = {row[1] for row in cursor.fetchall()}
			
			def safe_dict(row):
				d = dict(row)
				result = {}
				result["id"] = d.get("id")
				result["username"] = d.get("username", "")
				result["real_name"] = d.get("real_name", "")
				result["email"] = d.get("email", "")
				result["phone"] = d.get("phone", "")
				result["status"] = d.get("status", 1)
				result["create_at"] = d.get("create_at", "")
				result["update_at"] = d.get("update_at", "")
				return result
			
			if keyword:
				count_row = conn.execute(
					"SELECT COUNT(*) FROM users WHERE username LIKE ?",
					(f"%{keyword}%",)
				).fetchone()
				total = count_row[0]
				rows = conn.execute(
					"SELECT * FROM users WHERE username LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
					(f"%{keyword}%", page_size, offset)
				).fetchall()
			else:
				count_row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
				total = count_row[0]
				rows = conn.execute(
					"SELECT * FROM users ORDER BY id DESC LIMIT ? OFFSET ?",
					(page_size, offset)
				).fetchall()
			
			data_list = [safe_dict(row) for row in rows]
			
			for user in data_list:
				roles = conn.execute(
					"""SELECT DISTINCT r.id, r.role_name, r.role_code FROM roles r
					   INNER JOIN user_roles ur ON r.id = ur.role_id
					   WHERE ur.user_id=?""",
					(user["id"],)
				).fetchall()
				user["roles"] = [dict(r) for r in roles]
		
		return {"total": total, "page": page, "page_size": page_size, "data": data_list}

	@staticmethod
	def get_user_roles(user_id:int) -> list:
		with get_connection() as conn:
			rows = conn.execute(
				"""SELECT DISTINCT r.id, r.role_name, r.role_code FROM roles r
				   INNER JOIN user_roles ur ON r.id = ur.role_id
				   WHERE ur.user_id=?""",
				(user_id,)
			).fetchall()
		return [dict(r) for r in rows]

	@staticmethod
	def assign_roles(user_id:int, role_ids:list) -> bool:
		try:
			with get_connection() as conn:
				conn.execute("DELETE FROM user_roles WHERE user_id=?", (user_id,))
				for rid in role_ids:
					conn.execute(
						"INSERT INTO user_roles(user_id, role_id) VALUES(?,?)",
						(user_id, rid)
					)
			return True
		except sqlite3.IntegrityError:
			return False
