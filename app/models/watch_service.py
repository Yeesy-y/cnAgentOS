import sqlite3
import json
from urllib.parse import urlencode
from app.models.db import get_connection


def _normalize_source_row(row_dict: dict) -> dict:
	data = dict(row_dict)
	if data.get("url_template"):
		return data
	entry_url = data.get("entry_url", "") or ""
	url_params_json = data.get("url_params_json", "") or ""
	if entry_url:
		try:
			params_data = json.loads(url_params_json) if url_params_json else {}
			query_params = params_data.get("query_params", {}) if isinstance(params_data, dict) else {}
			if query_params:
				query = urlencode(query_params)
				data["url_template"] = f"{entry_url}?{query}"
			else:
				data["url_template"] = entry_url
		except Exception:
			data["url_template"] = entry_url
	else:
		data["url_template"] = ""
	return data


class WatchSourceRepository:
	@staticmethod
	def create_source(source_name: str, source_code: str, url_template: str, headers_json: str = None, cookie: str = None) -> int:
		try:
			with get_connection() as conn:
				cols = {row[1] for row in conn.execute("PRAGMA table_info(watch_sources)").fetchall()}
				if "url_template" in cols:
					cursor = conn.execute(
						"INSERT INTO watch_sources(source_name, source_code, url_template, headers_json, cookie) VALUES(?,?,?,?,?)",
						(source_name, source_code, url_template, headers_json, cookie)
					)
				else:
					entry_url = url_template.split("?", 1)[0]
					query_params = {}
					if "?" in url_template:
						from urllib.parse import urlparse, parse_qsl
						parsed = urlparse(url_template)
						query_params = dict(parse_qsl(parsed.query))
					url_params_json = json.dumps({"query_params": query_params}, ensure_ascii=False)
					cursor = conn.execute(
						"INSERT INTO watch_sources(source_name, source_code, entry_url, url_params_json, headers_json, cookie) VALUES(?,?,?,?,?,?)",
						(source_name, source_code, entry_url, url_params_json, headers_json or "", cookie or "")
					)
				return cursor.lastrowid
		except sqlite3.IntegrityError:
			return 0
	
	@staticmethod
	def get_source_by_id(source_id: int):
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM watch_sources WHERE id=?", (source_id,)).fetchone()
		return _normalize_source_row(dict(row)) if row else None
	
	@staticmethod
	def get_source_by_code(source_code: str):
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM watch_sources WHERE source_code=?", (source_code,)).fetchone()
		return _normalize_source_row(dict(row)) if row else None
	
	@staticmethod
	def list_sources(page: int = 1, page_size: int = 20, keyword: str = "") -> dict:
		offset = (page - 1) * page_size
		with get_connection() as conn:
			if keyword:
				count_row = conn.execute(
					"SELECT COUNT(*) FROM watch_sources WHERE source_name LIKE ? OR source_code LIKE ?",
					(f"%{keyword}%", f"%{keyword}%")
				).fetchone()
				total = count_row[0]
				rows = conn.execute(
					"SELECT * FROM watch_sources WHERE source_name LIKE ? OR source_code LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
					(f"%{keyword}%", f"%{keyword}%", page_size, offset)
				).fetchall()
			else:
				count_row = conn.execute("SELECT COUNT(*) FROM watch_sources").fetchone()
				total = count_row[0]
				rows = conn.execute(
					"SELECT * FROM watch_sources ORDER BY id DESC LIMIT ? OFFSET ?",
					(page_size, offset)
				).fetchall()
			
			data_list = [_normalize_source_row(dict(row)) for row in rows]
		
		return {"total": total, "page": page, "page_size": page_size, "data": data_list}
	
	@staticmethod
	def list_all_sources() -> list:
		with get_connection() as conn:
			rows = conn.execute("SELECT * FROM watch_sources WHERE status=1 ORDER BY id").fetchall()
		return [_normalize_source_row(dict(row)) for row in rows]
	
	@staticmethod
	def update_source(source_id: int, source_name: str = None, source_code: str = None, url_template: str = None, headers_json: str = None, cookie: str = None, status: int = None) -> bool:
		fields = []
		values = []
		
		with get_connection() as conn:
			cols = {row[1] for row in conn.execute("PRAGMA table_info(watch_sources)").fetchall()}
			
			if source_name is not None:
				fields.append("source_name=?")
				values.append(source_name)
			if source_code is not None:
				fields.append("source_code=?")
				values.append(source_code)
			if url_template is not None:
				if "url_template" in cols:
					fields.append("url_template=?")
					values.append(url_template)
				else:
					entry_url = url_template.split("?", 1)[0]
					query_params = {}
					if "?" in url_template:
						from urllib.parse import urlparse, parse_qsl
						parsed = urlparse(url_template)
						query_params = dict(parse_qsl(parsed.query))
					url_params_json = json.dumps({"query_params": query_params}, ensure_ascii=False)
					if "entry_url" in cols:
						fields.append("entry_url=?")
						values.append(entry_url)
					if "url_params_json" in cols:
						fields.append("url_params_json=?")
						values.append(url_params_json)
			if headers_json is not None:
				fields.append("headers_json=?")
				values.append(headers_json)
			if cookie is not None:
				fields.append("cookie=?")
				values.append(cookie)
			if status is not None:
				fields.append("status=?")
				values.append(status)
			
			if not fields:
				return False
			
			if "update_at" in cols:
				fields.append("update_at=datetime('now')")
			values.append(source_id)
			
			try:
				conn.execute(f"UPDATE watch_sources SET {','.join(fields)} WHERE id=?", values)
				return True
			except sqlite3.IntegrityError:
				return False
	
	@staticmethod
	def delete_source(source_id: int) -> bool:
		try:
			with get_connection() as conn:
				conn.execute("DELETE FROM watch_data WHERE source_id=?", (source_id,))
				conn.execute("DELETE FROM watch_sources WHERE id=?", (source_id,))
			return True
		except sqlite3.IntegrityError:
			return False


class WatchDataRepository:
	@staticmethod
	def create_data(source_id: int, keyword: str, title: str = None, content: str = None, url: str = None, publish_time: str = None) -> int:
		try:
			with get_connection() as conn:
				cursor = conn.execute(
					"INSERT INTO watch_data(source_id, keyword, title, content, url, publish_time) VALUES(?,?,?,?,?,?)",
					(source_id, keyword, title, content, url, publish_time)
				)
				return cursor.lastrowid
		except sqlite3.IntegrityError:
			return 0
	
	@staticmethod
	def get_data_by_id(data_id: int):
		with get_connection() as conn:
			row = conn.execute("""
				SELECT wd.*, ws.source_name 
				FROM watch_data wd 
				LEFT JOIN watch_sources ws ON wd.source_id = ws.id 
				WHERE wd.id=?
			""", (data_id,)).fetchone()
		return dict(row) if row else None
	
	@staticmethod
	def list_data(page: int = 1, page_size: int = 20, keyword: str = "") -> dict:
		offset = (page - 1) * page_size
		with get_connection() as conn:
			if keyword:
				count_row = conn.execute(
					"SELECT COUNT(*) FROM watch_data WHERE keyword LIKE ? OR title LIKE ? OR content LIKE ?",
					(f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
				).fetchone()
				total = count_row[0]
				rows = conn.execute("""
					SELECT wd.*, ws.source_name 
					FROM watch_data wd 
					LEFT JOIN watch_sources ws ON wd.source_id = ws.id 
					WHERE wd.keyword LIKE ? OR wd.title LIKE ? OR wd.content LIKE ? 
					ORDER BY wd.id DESC LIMIT ? OFFSET ?
				""", (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", page_size, offset)).fetchall()
			else:
				count_row = conn.execute("SELECT COUNT(*) FROM watch_data").fetchone()
				total = count_row[0]
				rows = conn.execute("""
					SELECT wd.*, ws.source_name 
					FROM watch_data wd 
					LEFT JOIN watch_sources ws ON wd.source_id = ws.id 
					ORDER BY wd.id DESC LIMIT ? OFFSET ?
				""", (page_size, offset)).fetchall()
			
			data_list = [dict(row) for row in rows]
		
		return {"total": total, "page": page, "page_size": page_size, "data": data_list}
	
	@staticmethod
	def delete_data(data_id: int) -> bool:
		try:
			with get_connection() as conn:
				conn.execute("DELETE FROM watch_data WHERE id=?", (data_id,))
			return True
		except sqlite3.IntegrityError:
			return False
	
	@staticmethod
	def delete_datas(data_ids: list) -> int:
		count = 0
		with get_connection() as conn:
			for did in data_ids:
				try:
					conn.execute("DELETE FROM watch_data WHERE id=?", (did,))
					count += 1
				except sqlite3.IntegrityError:
					pass
		return count
