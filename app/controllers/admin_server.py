import json
import tornado.web

from app.controllers.admin_base import AdminBaseHandler
from app.models.db import get_connection


class AdminServerListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		with get_connection() as conn:
			rows = conn.execute("""
				SELECT * FROM chat_servers ORDER BY status DESC, weight DESC, id ASC
			""").fetchall()
		
		servers = []
		for row in rows:
			servers.append({
				"id": row["id"],
				"name": row["name"],
				"host": row["host"],
				"port": row["port"],
				"status": row.get("status", "active"),
				"weight": row.get("weight", 100),
				"max_connections": row.get("max_connections", 1000),
				"current_connections": 0,
				"description": row.get("description", ""),
				"created_at": row["created_at"][:19] if row.get("created_at") else ""
			})
		
		active_count = len([s for s in servers if s["status"] == "active"])
		
		self.render(
			"admin_server_list.html",
			title="服务器管理",
			username=self.current_user,
			active_menu="server",
			servers=servers,
			active_count=active_count,
			total_count=len(servers)
		)
	
	def post(self):
		action = self.get_body_argument("action", "")
		
		if action == "add":
			self._add_server()
		elif action == "edit":
			self._edit_server()
		elif action == "delete":
			server_id_str = self.get_body_argument("server_id", "")
			if server_id_str and server_id_str.isdigit():
				self._delete_server(int(server_id_str))
		elif action == "toggle":
			server_id_str = self.get_body_argument("server_id", "")
			status = self.get_body_argument("status", "active")
			if server_id_str and server_id_str.isdigit():
				self._toggle_server(int(server_id_str), status)
		
		return self.redirect("/admin/server/list")
	
	def _add_server(self):
		name = (self.get_body_argument("name", "") or "").strip()
		host = (self.get_body_argument("host", "") or "").strip()
		port = int(self.get_body_argument("port", "9000"))
		weight = int(self.get_body_argument("weight", "100"))
		max_conn = int(self.get_body_argument("max_connections", "1000"))
		description = (self.get_body_argument("description", "") or "").strip()
		
		if not name or not host:
			return
		
		with get_connection() as conn:
			conn.execute("""
				INSERT INTO chat_servers (name, host, port, weight, max_connections, description, status)
				VALUES (?, ?, ?, ?, ?, ?, 'active')
			""", (name, host, port, weight, max_conn, description))
			conn.commit()
	
	def _edit_server(self):
		server_id = int(self.get_body_argument("server_id", "0"))
		name = (self.get_body_argument("name", "") or "").strip()
		host = (self.get_body_argument("host", "") or "").strip()
		port = int(self.get_body_argument("port", "9000"))
		weight = int(self.get_body_argument("weight", "100"))
		max_conn = int(self.get_body_argument("max_connections", "1000"))
		description = (self.get_body_argument("description", "") or "").strip()
		
		if not server_id or not name or not host:
			return
		
		with get_connection() as conn:
			conn.execute("""
				UPDATE chat_servers
				SET name = ?, host = ?, port = ?, weight = ?, max_connections = ?, description = ?
				WHERE id = ?
			""", (name, host, port, weight, max_conn, description, server_id))
			conn.commit()
	
	def _delete_server(self, server_id):
		with get_connection() as conn:
			conn.execute("DELETE FROM chat_servers WHERE id = ?", (server_id,))
			conn.commit()
	
	def _toggle_server(self, server_id, status):
		with get_connection() as conn:
			conn.execute("UPDATE chat_servers SET status = ? WHERE id = ?", (status, server_id))
			conn.commit()


class AdminServerStatusHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		with get_connection() as conn:
			servers = conn.execute("""
				SELECT id, name, status, weight, max_connections FROM chat_servers ORDER BY weight DESC
			""").fetchall()
		
		server_list = []
		for s in servers:
			server_list.append({
				"id": s["id"],
				"name": s["name"],
				"status": s["status"],
				"weight": s["weight"],
				"max_connections": s["max_connections"],
				"available": s["status"] == "active"
			})
		
		return self.write(json.dumps({"success": True, "servers": server_list}))


def get_available_server():
	with get_connection() as conn:
		row = conn.execute("""
			SELECT * FROM chat_servers
			WHERE status = 'active'
			ORDER BY weight DESC
			LIMIT 1
		""").fetchone()
	
	if row:
		return {
			"id": row["id"],
			"name": row["name"],
			"host": row["host"],
			"port": row["port"]
		}
	return None