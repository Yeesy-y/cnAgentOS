import sqlite3
import requests
from urllib.parse import urlencode
from app.models.db import get_connection

class ApiEndpointRepository:
	@staticmethod
	def create_api(api_name: str, api_code: str, api_url: str, request_method: str = "GET", response_format: str = "JSON", qps_limit: str = "", token: str = "", remark: str = "", status: int = 1) -> int:
		api_name = (api_name or "").strip()
		api_code = (api_code or "").strip()
		api_url = (api_url or "").strip()
		request_method = (request_method or "GET").strip().upper()
		response_format = (response_format or "JSON").strip().upper()
		qps_limit = (qps_limit or "").strip()
		token = (token or "").strip()
		remark = (remark or "").strip()
		try:
			with get_connection() as conn:
				cursor = conn.execute(
					"""
					INSERT INTO api_endpoints(api_name, api_code, api_url, request_method, response_format, qps_limit, token, remark, status)
					VALUES(?,?,?,?,?,?,?,?,?)
					""",
					(api_name, api_code, api_url, request_method, response_format, qps_limit, token, remark, int(status))
				)
				return cursor.lastrowid
		except sqlite3.IntegrityError:
			return 0

	@staticmethod
	def get_api_by_id(api_id: int):
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM api_endpoints WHERE id=?", (api_id,)).fetchone()
		return dict(row) if row else None

	@staticmethod
	def get_api_by_code(api_code: str):
		api_code = (api_code or "").strip()
		if not api_code:
			return None
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM api_endpoints WHERE api_code=?", (api_code,)).fetchone()
		return dict(row) if row else None

	@staticmethod
	def update_api(api_id: int, api_name: str = None, api_code: str = None, api_url: str = None, request_method: str = None, response_format: str = None, qps_limit: str = None, token: str = None, remark: str = None, status: int = None) -> bool:
		fields = []
		values = []

		if api_name is not None:
			fields.append("api_name=?")
			values.append((api_name or "").strip())
		if api_code is not None:
			fields.append("api_code=?")
			values.append((api_code or "").strip())
		if api_url is not None:
			fields.append("api_url=?")
			values.append((api_url or "").strip())
		if request_method is not None:
			fields.append("request_method=?")
			values.append((request_method or "GET").strip().upper())
		if response_format is not None:
			fields.append("response_format=?")
			values.append((response_format or "JSON").strip().upper())
		if qps_limit is not None:
			fields.append("qps_limit=?")
			values.append((qps_limit or "").strip())
		if token is not None:
			fields.append("token=?")
			values.append((token or "").strip())
		if remark is not None:
			fields.append("remark=?")
			values.append((remark or "").strip())
		if status is not None:
			fields.append("status=?")
			values.append(int(status))

		if not fields:
			return False

		fields.append("update_at=datetime('now')")
		values.append(api_id)
		try:
			with get_connection() as conn:
				conn.execute(f"UPDATE api_endpoints SET {','.join(fields)} WHERE id=?", values)
			return True
		except sqlite3.IntegrityError:
			return False

	@staticmethod
	def delete_api(api_id: int) -> bool:
		try:
			with get_connection() as conn:
				conn.execute("DELETE FROM api_endpoints WHERE id=?", (api_id,))
			return True
		except sqlite3.IntegrityError:
			return False

	@staticmethod
	def list_apis(page: int = 1, page_size: int = 20, keyword: str = "") -> dict:
		page = max(1, int(page or 1))
		page_size = max(1, int(page_size or 20))
		offset = (page - 1) * page_size
		keyword = (keyword or "").strip()

		with get_connection() as conn:
			if keyword:
				count_row = conn.execute(
					"SELECT COUNT(*) FROM api_endpoints WHERE api_name LIKE ? OR api_code LIKE ? OR api_url LIKE ?",
					(f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
				).fetchone()
				total = count_row[0]
				rows = conn.execute(
					"""
					SELECT * FROM api_endpoints
					WHERE api_name LIKE ? OR api_code LIKE ? OR api_url LIKE ?
					ORDER BY id DESC
					LIMIT ? OFFSET ?
					""",
					(f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", page_size, offset)
				).fetchall()
			else:
				count_row = conn.execute("SELECT COUNT(*) FROM api_endpoints").fetchone()
				total = count_row[0]
				rows = conn.execute(
					"SELECT * FROM api_endpoints ORDER BY id DESC LIMIT ? OFFSET ?",
					(page_size, offset)
				).fetchall()

		return {"total": total, "page": page, "page_size": page_size, "data": [dict(r) for r in rows]}

	@staticmethod
	def call_api(api_code: str, params: dict = None, timeout: int = 30) -> dict:
		api = ApiEndpointRepository.get_api_by_code(api_code)
		if not api:
			return {"success": False, "message": "接口不存在", "status_code": 404}
		if int(api.get("status") or 0) != 1:
			return {"success": False, "message": "接口已禁用", "status_code": 403}

		method = (api.get("request_method") or "GET").strip().upper()
		url = (api.get("api_url") or "").strip()
		if not url:
			return {"success": False, "message": "接口URL为空", "status_code": 400}

		headers = {}
		token = (api.get("token") or "").strip()
		if token:
			headers["Authorization"] = f"Bearer {token}"

		params = params or {}
		try:
			if method == "GET":
				if params:
					sep = "&" if "?" in url else "?"
					url = url + sep + urlencode(params, doseq=True)
				resp = requests.get(url, headers=headers, timeout=timeout)
			else:
				resp = requests.post(url, headers=headers, data=params, timeout=timeout)
			content_type = (resp.headers.get("Content-Type") or "").lower()
			if "application/json" in content_type:
				return {"success": True, "status_code": resp.status_code, "data": resp.json()}
			return {"success": True, "status_code": resp.status_code, "data": resp.text}
		except Exception as e:
			return {"success": False, "message": str(e), "status_code": 500}
