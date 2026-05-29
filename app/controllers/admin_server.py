import json
import time
import threading
import tornado.web
import urllib.request
import urllib.error

from app.controllers.admin_base import AdminBaseHandler
from app.models.db import get_connection

# 当前活跃服务器
_current_server = None
_current_server_lock = threading.Lock()
_last_check_time = 0
_CHECK_INTERVAL = 30  # 健康检查间隔（秒）


def check_server_health(host, port, timeout=5):
	"""检查服务器健康状态"""
	try:
		url = f"http://{host}:{port}/health"
		req = urllib.request.Request(url, method='GET', timeout=timeout)
		with urllib.request.urlopen(req, timeout=timeout) as response:
			if response.status == 200:
				try:
					data = json.loads(response.read().decode('utf-8'))
					return {
						"healthy": True,
						"latency": data.get("latency", 0),
						"message": "健康"
					}
				except:
					return {"healthy": True, "latency": 0, "message": "响应正常"}
		return {"healthy": False, "latency": 0, "message": f"状态码: {response.status}"}
	except urllib.error.HTTPError as e:
		return {"healthy": False, "latency": 0, "message": f"HTTP错误: {e.code}"}
	except urllib.error.URLError as e:
		return {"healthy": False, "latency": 0, "message": f"连接失败: {str(e)}"}
	except Exception as e:
		return {"healthy": False, "latency": 0, "message": f"未知错误: {str(e)}"}


class AdminServerListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		with get_connection() as conn:
			rows = conn.execute("""
				SELECT * FROM chat_servers ORDER BY status DESC, weight DESC, id ASC
			""").fetchall()
		
		servers = []
		for row in rows:
			health = None
			if row.get("status") == "active":
				health = check_server_health(row["host"], row["port"])
			
			is_current = False
			global _current_server
			if _current_server and _current_server["id"] == row["id"]:
				is_current = True
			
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
				"created_at": row["created_at"][:19] if row.get("created_at") else "",
				"healthy": health["healthy"] if health else None,
				"health_message": health["message"] if health else "",
				"latency": health["latency"] if health else 0,
				"is_current": is_current
			})
		
		active_count = len([s for s in servers if s["status"] == "active"])
		healthy_count = len([s for s in servers if s["status"] == "active" and s["healthy"]])
		
		self.render(
			"admin_server_list.html",
			title="服务器管理",
			username=self.current_user,
			active_menu="server",
			servers=servers,
			active_count=active_count,
			healthy_count=healthy_count,
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


class AdminServerSwitchHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		server_id_str = self.get_body_argument("server_id", "")
		if not server_id_str or not server_id_str.isdigit():
			return self.write(json.dumps({"success": False, "message": "无效的服务器ID"}))
		
		server_id = int(server_id_str)
		result = switch_to_server(server_id)
		
		if result:
			return self.write(json.dumps({"success": True, "message": "切换成功"}))
		else:
			return self.write(json.dumps({"success": False, "message": "切换失败，服务器不存在或未启用"}))


class AdminServerStatusHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		with get_connection() as conn:
			servers = conn.execute("""
				SELECT id, name, status, weight, max_connections, host, port FROM chat_servers ORDER BY weight DESC
			""").fetchall()
		
		server_list = []
		for s in servers:
			health = None
			if s["status"] == "active":
				health = check_server_health(s["host"], s["port"])
			
			server_list.append({
				"id": s["id"],
				"name": s["name"],
				"status": s["status"],
				"weight": s["weight"],
				"max_connections": s["max_connections"],
				"available": s["status"] == "active",
				"healthy": health["healthy"] if health else False,
				"health_message": health["message"] if health else ""
			})
		
		return self.write(json.dumps({"success": True, "servers": server_list}))


def get_available_server(force_check=False):
	"""获取可用的聊天服务器，支持自动健康检查和故障切换"""
	global _current_server, _last_check_time, _CHECK_INTERVAL
	
	# 获取所有活跃服务器
	with get_connection() as conn:
		rows = conn.execute("""
			SELECT * FROM chat_servers
			WHERE status = 'active'
			ORDER BY weight DESC, id ASC
		""").fetchall()
	
	if not rows:
		return None
	
	# 如果需要强制检查或超过检查间隔，执行健康检查
	now = time.time()
	if force_check or now - _last_check_time >= _CHECK_INTERVAL or _current_server is None:
		_last_check_time = now
		
		# 检查所有活跃服务器的健康状态
		healthy_servers = []
		for row in rows:
			health = check_server_health(row["host"], row["port"])
			if health["healthy"]:
				healthy_servers.append({
					"id": row["id"],
					"name": row["name"],
					"host": row["host"],
					"port": row["port"],
					"weight": row["weight"],
					"latency": health["latency"]
				})
		
		if not healthy_servers:
			# 没有健康服务器，返回None
			_current_server = None
			return None
		
		# 按权重排序，权重相同则按延迟排序
		healthy_servers.sort(key=lambda x: (-x["weight"], x["latency"]))
		
		# 选择最优服务器
		best_server = healthy_servers[0]
		
		# 检查是否需要切换
		if _current_server is None or _current_server["id"] != best_server["id"]:
			# 记录切换日志
			if _current_server:
				print(f"[SERVER_SWITCH] 从 {_current_server['name']}({_current_server['host']}:{_current_server['port']}) "
					  f"切换到 {best_server['name']}({best_server['host']}:{best_server['port']})")
			else:
				print(f"[SERVER_SWITCH] 初始化连接到 {best_server['name']}({best_server['host']}:{best_server['port']})")
			
			_current_server = best_server
	
	return _current_server


def get_current_server_info():
	"""获取当前活跃服务器信息"""
	global _current_server
	return _current_server if _current_server else None


def switch_to_server(server_id):
	"""手动切换到指定服务器"""
	global _current_server
	
	with get_connection() as conn:
		row = conn.execute("""
			SELECT * FROM chat_servers
			WHERE id = ? AND status = 'active'
		""", (server_id,)).fetchone()
	
	if row:
		old_server = _current_server
		_current_server = {
			"id": row["id"],
			"name": row["name"],
			"host": row["host"],
			"port": row["port"]
		}
		
		if old_server:
			print(f"[SERVER_SWITCH] 手动切换: 从 {old_server['name']} 切换到 {_current_server['name']}")
		return True
	return False