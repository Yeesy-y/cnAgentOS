import sqlite3
from app.models.db import get_connection

class ModelServiceRepository:
	@staticmethod
	def create_model(model_name: str, model_code: str, api_key: str, base_url: str, model_id: str, is_default: int = 0) -> int:
		try:
			with get_connection() as conn:
				if is_default == 1:
					conn.execute("UPDATE model_services SET is_default = 0 WHERE is_default = 1")
				cursor = conn.execute(
					"INSERT INTO model_services(model_name, model_code, api_key, base_url, model_id, is_default, token_used) VALUES(?,?,?,?,?,?,0)",
					(model_name, model_code, api_key, base_url, model_id, is_default)
				)
				return cursor.lastrowid
		except sqlite3.IntegrityError:
			return 0
	
	@staticmethod
	def get_model_by_id(model_id: int):
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM model_services WHERE id=?", (model_id,)).fetchone()
		return dict(row) if row else None
	
	@staticmethod
	def get_model_by_code(model_code: str):
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM model_services WHERE model_code=?", (model_code,)).fetchone()
		return dict(row) if row else None
	
	@staticmethod
	def get_default_model():
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM model_services WHERE is_default=1 AND status=1").fetchone()
		return dict(row) if row else None
	
	@staticmethod
	def list_models(page: int = 1, page_size: int = 6, keyword: str = "") -> dict:
		offset = (page - 1) * page_size
		with get_connection() as conn:
			if keyword:
				count_row = conn.execute(
					"SELECT COUNT(*) FROM model_services WHERE model_name LIKE ? OR model_code LIKE ?",
					(f"%{keyword}%", f"%{keyword}%")
				).fetchone()
				total = count_row[0]
				rows = conn.execute(
					"SELECT * FROM model_services WHERE model_name LIKE ? OR model_code LIKE ? ORDER BY is_default DESC, id DESC LIMIT ? OFFSET ?",
					(f"%{keyword}%", f"%{keyword}%", page_size, offset)
				).fetchall()
			else:
				count_row = conn.execute("SELECT COUNT(*) FROM model_services").fetchone()
				total = count_row[0]
				rows = conn.execute(
					"SELECT * FROM model_services ORDER BY is_default DESC, id DESC LIMIT ? OFFSET ?",
					(page_size, offset)
				).fetchall()
			
			data_list = [dict(row) for row in rows]
		
		return {"total": total, "page": page, "page_size": page_size, "data": data_list}
	
	@staticmethod
	def update_model(model_id: int, model_name: str = None, model_code: str = None, api_key: str = None, base_url: str = None, model_id_param: str = None, is_default: int = None, status: int = None) -> bool:
		fields = []
		values = []
		
		if model_name is not None:
			fields.append("model_name=?")
			values.append(model_name)
		if model_code is not None:
			fields.append("model_code=?")
			values.append(model_code)
		if api_key is not None:
			fields.append("api_key=?")
			values.append(api_key)
		if base_url is not None:
			fields.append("base_url=?")
			values.append(base_url)
		if model_id_param is not None:
			fields.append("model_id=?")
			values.append(model_id_param)
		if is_default is not None:
			fields.append("is_default=?")
			values.append(is_default)
		if status is not None:
			fields.append("status=?")
			values.append(status)
		
		if not fields:
			return False
		
		fields.append("update_at=datetime('now')")
		values.append(model_id)
		
		try:
			with get_connection() as conn:
				if is_default == 1:
					conn.execute("UPDATE model_services SET is_default = 0 WHERE is_default = 1 AND id != ?", (model_id,))
				conn.execute(f"UPDATE model_services SET {','.join(fields)} WHERE id=?", values)
			return True
		except sqlite3.IntegrityError:
			return False
	
	@staticmethod
	def delete_model(model_id: int) -> bool:
		try:
			with get_connection() as conn:
				conn.execute("DELETE FROM model_services WHERE id=?", (model_id,))
			return True
		except sqlite3.IntegrityError:
			return False
	
	@staticmethod
	def increment_token_usage(model_id: int, tokens: int) -> bool:
		try:
			with get_connection() as conn:
				conn.execute("UPDATE model_services SET token_used = token_used + ?, update_at=datetime('now') WHERE id=?", (tokens, model_id))
			return True
		except sqlite3.IntegrityError:
			return False
