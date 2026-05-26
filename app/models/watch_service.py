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
					SELECT wd.*, ws.source_name, wdd.deep_status, wdd.detail_title, wdd.detail_summary, wdd.detail_keywords, wdd.detail_content
					FROM watch_data wd
					LEFT JOIN watch_sources ws ON wd.source_id = ws.id
					LEFT JOIN watch_data_detail wdd ON wd.id = wdd.data_id
					WHERE wd.keyword LIKE ? OR wd.title LIKE ? OR wd.content LIKE ?
					ORDER BY wd.id DESC LIMIT ? OFFSET ?
				""", (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", page_size, offset)).fetchall()
			else:
				count_row = conn.execute("SELECT COUNT(*) FROM watch_data").fetchone()
				total = count_row[0]
				rows = conn.execute("""
					SELECT wd.*, ws.source_name, wdd.deep_status, wdd.detail_title, wdd.detail_summary, wdd.detail_keywords, wdd.detail_content
					FROM watch_data wd
					LEFT JOIN watch_sources ws ON wd.source_id = ws.id
					LEFT JOIN watch_data_detail wdd ON wd.id = wdd.data_id
					ORDER BY wd.id DESC LIMIT ? OFFSET ?
				""", (page_size, offset)).fetchall()
			
			data_list = [dict(row) for row in rows]
		
		return {"total": total, "page": page, "page_size": page_size, "data": data_list}
	
	@staticmethod
	def delete_data(data_id: int) -> bool:
		try:
			with get_connection() as conn:
				conn.execute("DELETE FROM watch_data_detail WHERE data_id=?", (data_id,))
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
					conn.execute("DELETE FROM watch_data_detail WHERE data_id=?", (did,))
					conn.execute("DELETE FROM watch_data WHERE id=?", (did,))
					count += 1
				except sqlite3.IntegrityError:
					pass
		return count


class WatchDataDetailRepository:
	@staticmethod
	def create_detail(data_id: int, source_id: int, detail_title: str = None, detail_content: str = None,
	                  detail_summary: str = None, detail_keywords: str = None, source_url: str = None,
	                  ai_model: str = None, tokens_used: int = 0) -> int:
		with get_connection() as conn:
			cursor = conn.execute(
				"INSERT INTO watch_data_detail(data_id, source_id, detail_title, detail_content, detail_summary, detail_keywords, source_url, ai_model, tokens_used) VALUES(?,?,?,?,?,?,?,?,?)",
				(data_id, source_id, detail_title, detail_content, detail_summary, detail_keywords, source_url, ai_model, tokens_used)
			)
			return cursor.lastrowid

	@staticmethod
	def update_detail(detail_id: int, detail_title: str = None, detail_content: str = None,
	                  detail_summary: str = None, detail_keywords: str = None,
	                  deep_status: int = None, error_msg: str = None, tokens_used: int = None) -> bool:
		fields = []
		values = []
		if detail_title is not None:
			fields.append("detail_title=?"); values.append(detail_title)
		if detail_content is not None:
			fields.append("detail_content=?"); values.append(detail_content)
		if detail_summary is not None:
			fields.append("detail_summary=?"); values.append(detail_summary)
		if detail_keywords is not None:
			fields.append("detail_keywords=?"); values.append(detail_keywords)
		if deep_status is not None:
			fields.append("deep_status=?"); values.append(deep_status)
		if error_msg is not None:
			fields.append("error_msg=?"); values.append(error_msg)
		if tokens_used is not None:
			fields.append("tokens_used=?"); values.append(tokens_used)
		if not fields:
			return False
		values.append(detail_id)
		with get_connection() as conn:
			conn.execute(f"UPDATE watch_data_detail SET {','.join(fields)} WHERE id=?", values)
		return True

	@staticmethod
	def get_detail_by_data_id(data_id: int):
		with get_connection() as conn:
			row = conn.execute(
				"SELECT * FROM watch_data_detail WHERE data_id=? ORDER BY id DESC LIMIT 1",
				(data_id,)
			).fetchone()
		return dict(row) if row else None

	@staticmethod
	def get_details_by_data_ids(data_ids: list) -> dict:
		result = {}
		if not data_ids:
			return result
		placeholders = ",".join("?" for _ in data_ids)
		with get_connection() as conn:
			rows = conn.execute(
				f"SELECT * FROM watch_data_detail WHERE data_id IN ({placeholders}) ORDER BY id DESC",
				data_ids
			).fetchall()
		for row in rows:
			d = dict(row)
			did = d["data_id"]
			if did not in result:
				result[did] = d
		return result

	@staticmethod
	def delete_detail_by_data_id(data_id: int) -> bool:
		with get_connection() as conn:
			conn.execute("DELETE FROM watch_data_detail WHERE data_id=?", (data_id,))
		return True

	@staticmethod
	def get_deep_statistics() -> dict:
		with get_connection() as conn:
			total = conn.execute("SELECT COUNT(*) FROM watch_data_detail").fetchone()[0]
			completed = conn.execute(
				"SELECT COUNT(*) FROM watch_data_detail WHERE deep_status=2"
			).fetchone()[0]
			failed = conn.execute(
				"SELECT COUNT(*) FROM watch_data_detail WHERE deep_status=3"
			).fetchone()[0]
			pending = conn.execute(
				"SELECT COUNT(*) FROM watch_data_detail WHERE deep_status=0"
			).fetchone()[0]
			total_tokens = conn.execute(
				"SELECT COALESCE(SUM(tokens_used), 0) FROM watch_data_detail"
			).fetchone()[0]
		return {
			"total": total,
			"completed": completed,
			"failed": failed,
			"pending": pending,
			"total_tokens": total_tokens
		}
