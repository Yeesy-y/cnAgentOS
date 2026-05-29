import os
import json
import hashlib
import math
import tornado.web

from app.controllers.admin_base import AdminBaseHandler
from app.models.db import get_connection


def format_size(bytes):
	if bytes == 0:
		return '0 B'
	k = 1024
	sizes = ['B', 'KB', 'MB', 'GB', 'TB']
	i = min(int(math.log(bytes, k)) if bytes > 0 else 0, len(sizes) - 1)
	return f"{bytes / k**i:.2f} {sizes[i]}"


class AdminFileListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		page = int(self.get_argument("page", "1"))
		keyword = (self.get_argument("keyword", "") or "").strip()
		file_type = (self.get_argument("file_type", "") or "").strip()
		page_size = 20
		
		upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads")
		
		with get_connection() as conn:
			query = """
				SELECT cf.*, u.username as uploader_name
				FROM chat_files cf
				LEFT JOIN users u ON cf.uploader_id = u.id
				WHERE 1=1
			"""
			params = []
			
			if keyword:
				query += " AND cf.original_name LIKE ?"
				params.append(f"%{keyword}%")
			
			if file_type:
				if file_type == "image":
					query += " AND cf.content_type LIKE ?"
					params.append("%image%")
				elif file_type == "video":
					query += " AND cf.content_type LIKE ?"
					params.append("%video%")
				elif file_type == "audio":
					query += " AND cf.content_type LIKE ?"
					params.append("%audio%")
				else:
					query += " AND (cf.content_type IS NULL OR cf.content_type NOT LIKE ? AND cf.content_type NOT LIKE ? AND cf.content_type NOT LIKE ?)"
					params.extend(["%image%", "%video%", "%audio%"])
			
			count_query = query.replace("SELECT cf.*, u.username as uploader_name", "SELECT COUNT(*) as cnt")
			count_row = conn.execute(count_query, tuple(params)).fetchone()
			total = count_row["cnt"] if count_row else 0
			
			offset = (page - 1) * page_size
			query += " ORDER BY cf.created_at DESC LIMIT ? OFFSET ?"
			params.extend([page_size, offset])
			
			rows = conn.execute(query, tuple(params)).fetchall()
		
		all_hashes = {}
		all_rows = conn.execute("SELECT file_hash, COUNT(*) as cnt FROM chat_files WHERE file_hash IS NOT NULL AND file_hash != '' GROUP BY file_hash").fetchall()
		for r in all_rows:
			all_hashes[r["file_hash"]] = r["cnt"]
		
		files = []
		for row in rows:
			file_path = os.path.join(upload_dir, row["stored_name"]) if row["stored_name"] else ""
			file_exists = os.path.exists(file_path) if file_path else False
			file_hash = row.get("file_hash", "")
			is_duplicate = file_hash and all_hashes.get(file_hash, 0) > 1
			
			files.append({
				"id": row["id"],
				"original_name": row["original_name"],
				"stored_name": row["stored_name"],
				"file_path": "/static/uploads/" + row["stored_name"] if row["stored_name"] and file_exists else "",
				"file_size": row["file_size"],
				"content_type": row["content_type"],
				"file_hash": file_hash,
				"uploader_name": row["uploader_name"] or "未知",
				"created_at": row["created_at"][:19] if row.get("created_at") else "",
				"exists": file_exists,
				"is_duplicate": is_duplicate
			})
		
		total_size_result = conn.execute("SELECT COALESCE(SUM(file_size), 0) as total FROM chat_files").fetchone()
		total_size = total_size_result["total"]
		
		unique_hashes_result = conn.execute("SELECT COUNT(DISTINCT file_hash) as cnt FROM chat_files WHERE file_hash IS NOT NULL AND file_hash != ''").fetchone()
		unique_hashes = unique_hashes_result["cnt"]
		
		unique_size_result = conn.execute("""
			SELECT COALESCE(SUM(file_size), 0) as total FROM (
				SELECT file_hash, MAX(file_size) as file_size FROM chat_files 
				WHERE file_hash IS NOT NULL AND file_hash != '' 
				GROUP BY file_hash
			)
		""").fetchone()
		unique_size = unique_size_result["total"]
		saved_space = total_size - unique_size
		
		self.render(
			"admin_file_list.html",
			title="文件管理",
			username=self.current_user,
			active_menu="file",
			files=files,
			total=total,
			page=page,
			page_size=page_size,
			keyword=keyword,
			file_type=file_type,
			total_size=format_size(total_size),
			unique_hashes=unique_hashes,
			saved_space=format_size(saved_space)
		)
	
	def post(self):
		action = self.get_body_argument("action", "")
		upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads")
		
		if action == "delete":
			file_id_str = self.get_body_argument("file_id", "")
			if file_id_str and file_id_str.isdigit():
				self._delete_file(int(file_id_str), upload_dir)
		elif action == "batch_delete":
			file_ids_str = self.get_body_argument("file_ids", "")
			if file_ids_str:
				file_ids = [int(x.strip()) for x in file_ids_str.split(",") if x.strip().isdigit()]
				for fid in file_ids:
					self._delete_file(fid, upload_dir)
		elif action == "cleanup":
			self._cleanup_duplicate_files(upload_dir)
		
		return self.redirect("/admin/file/list")
	
	def _delete_file(self, file_id, upload_dir):
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM chat_files WHERE id = ?", (file_id,)).fetchone()
			if row and row["stored_name"]:
				file_path = os.path.join(upload_dir, row["stored_name"])
				if os.path.exists(file_path):
					try:
						os.remove(file_path)
					except:
						pass
			conn.execute("DELETE FROM chat_files WHERE id = ?", (file_id,))
			conn.commit()
	
	def _cleanup_duplicate_files(self, upload_dir):
		with get_connection() as conn:
			rows = conn.execute("""
				SELECT file_hash, MIN(id) as keep_id, COUNT(*) as cnt
				FROM chat_files
				WHERE file_hash IS NOT NULL AND file_hash != ''
				GROUP BY file_hash
				HAVING COUNT(*) > 1
			""").fetchall()
			
			for row in rows:
				file_hash = row["file_hash"]
				keep_id = row["keep_id"]
				
				duplicates = conn.execute("""
					SELECT id, stored_name FROM chat_files
					WHERE file_hash = ? AND id != ?
				""", (file_hash, keep_id)).fetchall()
				
				for dup in duplicates:
					if dup["stored_name"]:
						file_path = os.path.join(upload_dir, dup["stored_name"])
						if os.path.exists(file_path):
							try:
								os.remove(file_path)
							except:
								pass
					conn.execute("DELETE FROM chat_files WHERE id = ?", (dup["id"],))
				
				conn.commit()


class AdminFileStatsHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads")
		
		with get_connection() as conn:
			total_files = conn.execute("SELECT COUNT(*) as cnt FROM chat_files").fetchone()["cnt"]
			total_size = conn.execute("SELECT COALESCE(SUM(file_size), 0) as total FROM chat_files").fetchone()["total"]
			
			hashes = conn.execute("""
				SELECT COUNT(DISTINCT file_hash) as cnt
				FROM chat_files
				WHERE file_hash IS NOT NULL AND file_hash != ''
			""").fetchone()["cnt"]
			
			duplicate_files = conn.execute("""
				SELECT COUNT(*) as cnt FROM (
					SELECT file_hash FROM chat_files
					WHERE file_hash IS NOT NULL AND file_hash != ''
					GROUP BY file_hash HAVING COUNT(*) > 1
				)
			""").fetchone()["cnt"]
		
		physical_size = 0
		if os.path.exists(upload_dir):
			for f in os.listdir(upload_dir):
				fp = os.path.join(upload_dir, f)
				if os.path.isfile(fp):
					physical_size += os.path.getsize(fp)
		
		return self.write(json.dumps({
			"success": True,
			"stats": {
				"total_files": total_files,
				"total_size": total_size,
				"unique_hashes": hashes,
				"duplicate_files": duplicate_files,
				"physical_size": physical_size
			}
		}))


def save_chat_file(uploader_id, original_filename, file_body, content_type):
	import uuid
	
	file_hash = hashlib.md5(file_body).hexdigest()
	file_ext = os.path.splitext(original_filename)[1]
	new_filename = f"{uuid.uuid4().hex}{file_ext}"
	
	upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "uploads")
	if not os.path.exists(upload_dir):
		os.makedirs(upload_dir)
	
	existing = None
	with get_connection() as conn:
		existing = conn.execute("""
			SELECT id, stored_name FROM chat_files
			WHERE file_hash = ?
		""", (file_hash,)).fetchone()
		
		if existing:
			return existing["id"], existing["stored_name"], False
	
	file_path = os.path.join(upload_dir, new_filename)
	with open(file_path, 'wb') as f:
		f.write(file_body)
	
	with get_connection() as conn:
		cursor = conn.execute("""
			INSERT INTO chat_files (original_name, stored_name, file_size, content_type, file_hash, uploader_id)
			VALUES (?, ?, ?, ?, ?, ?)
		""", (original_filename, new_filename, len(file_body), content_type, file_hash, uploader_id))
		file_id = cursor.lastrowid
		conn.commit()
	
	return file_id, new_filename, True