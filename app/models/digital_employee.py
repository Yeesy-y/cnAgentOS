import json
import sqlite3
from app.models.db import get_connection


def _normalize_json_text(value) -> str:
	if value is None:
		return ""
	if isinstance(value, (dict, list)):
		try:
			return json.dumps(value, ensure_ascii=False)
		except Exception:
			return ""
	text = (value or "").strip()
	if not text:
		return ""
	try:
		obj = json.loads(text)
		return json.dumps(obj, ensure_ascii=False)
	except Exception:
		return text


class DigitalEmployeeRepository:
	@staticmethod
	def create_employee(employee_name: str, employee_code: str, at_alias: str, category: int = 1, service_type: str = "LLM", description: str = "", model_code: str = "", prompt: str = "", api_code: str = "", config_json: str = "", status: int = 1) -> int:
		employee_name = (employee_name or "").strip()
		employee_code = (employee_code or "").strip()
		at_alias = (at_alias or "").strip()
		service_type = (service_type or "LLM").strip().upper()
		description = (description or "").strip()
		model_code = (model_code or "").strip()
		prompt = (prompt or "").strip()
		api_code = (api_code or "").strip()
		config_json = _normalize_json_text(config_json)
		try:
			with get_connection() as conn:
				cursor = conn.execute(
					"""
					INSERT INTO digital_employees(employee_name, employee_code, at_alias, category, service_type, description, model_code, prompt, api_code, config_json, status)
					VALUES(?,?,?,?,?,?,?,?,?,?,?)
					""",
					(employee_name, employee_code, at_alias, int(category), service_type, description, model_code, prompt, api_code, config_json, int(status))
				)
				return cursor.lastrowid
		except sqlite3.IntegrityError:
			return 0

	@staticmethod
	def get_by_id(employee_id: int):
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM digital_employees WHERE id=?", (int(employee_id),)).fetchone()
		return dict(row) if row else None

	@staticmethod
	def get_by_code(employee_code: str):
		employee_code = (employee_code or "").strip()
		if not employee_code:
			return None
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM digital_employees WHERE employee_code=?", (employee_code,)).fetchone()
		return dict(row) if row else None

	@staticmethod
	def get_by_alias(at_alias: str):
		at_alias = (at_alias or "").strip()
		if not at_alias:
			return None
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM digital_employees WHERE at_alias=?", (at_alias,)).fetchone()
		return dict(row) if row else None

	@staticmethod
	def list_employees(page: int = 1, page_size: int = 20, keyword: str = "") -> dict:
		page = max(1, int(page or 1))
		page_size = max(1, int(page_size or 20))
		offset = (page - 1) * page_size
		keyword = (keyword or "").strip()
		with get_connection() as conn:
			if keyword:
				count_row = conn.execute(
					"""
					SELECT COUNT(*) FROM digital_employees
					WHERE employee_name LIKE ? OR employee_code LIKE ? OR at_alias LIKE ?
					""",
					(f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
				).fetchone()
				total = count_row[0]
				rows = conn.execute(
					"""
					SELECT * FROM digital_employees
					WHERE employee_name LIKE ? OR employee_code LIKE ? OR at_alias LIKE ?
					ORDER BY id DESC
					LIMIT ? OFFSET ?
					""",
					(f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", page_size, offset)
				).fetchall()
			else:
				count_row = conn.execute("SELECT COUNT(*) FROM digital_employees").fetchone()
				total = count_row[0]
				rows = conn.execute(
					"SELECT * FROM digital_employees ORDER BY id DESC LIMIT ? OFFSET ?",
					(page_size, offset)
				).fetchall()
		return {"total": total, "page": page, "page_size": page_size, "data": [dict(r) for r in rows]}

	@staticmethod
	def update_employee(employee_id: int, employee_name: str = None, employee_code: str = None, at_alias: str = None, category: int = None, service_type: str = None, description: str = None, model_code: str = None, prompt: str = None, api_code: str = None, config_json: str = None, status: int = None) -> bool:
		fields = []
		values = []
		if employee_name is not None:
			fields.append("employee_name=?")
			values.append((employee_name or "").strip())
		if employee_code is not None:
			fields.append("employee_code=?")
			values.append((employee_code or "").strip())
		if at_alias is not None:
			fields.append("at_alias=?")
			values.append((at_alias or "").strip())
		if category is not None:
			fields.append("category=?")
			values.append(int(category))
		if service_type is not None:
			fields.append("service_type=?")
			values.append((service_type or "LLM").strip().upper())
		if description is not None:
			fields.append("description=?")
			values.append((description or "").strip())
		if model_code is not None:
			fields.append("model_code=?")
			values.append((model_code or "").strip())
		if prompt is not None:
			fields.append("prompt=?")
			values.append((prompt or "").strip())
		if api_code is not None:
			fields.append("api_code=?")
			values.append((api_code or "").strip())
		if config_json is not None:
			fields.append("config_json=?")
			values.append(_normalize_json_text(config_json))
		if status is not None:
			fields.append("status=?")
			values.append(int(status))

		if not fields:
			return False

		fields.append("update_at=datetime('now')")
		values.append(int(employee_id))
		try:
			with get_connection() as conn:
				conn.execute(f"UPDATE digital_employees SET {','.join(fields)} WHERE id=?", values)
			return True
		except sqlite3.IntegrityError:
			return False

	@staticmethod
	def delete_employee(employee_id: int) -> bool:
		try:
			with get_connection() as conn:
				conn.execute("DELETE FROM digital_employees WHERE id=?", (int(employee_id),))
			return True
		except sqlite3.IntegrityError:
			return False
