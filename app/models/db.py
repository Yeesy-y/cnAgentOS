# 数据库链接与建表
import os
import sqlite3
import hashlib
import secrets
import json

# 获得项目根路径的方法
def _project_root():
	return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir,os.pardir))

# 获得数据文件路径
DB_PATH = os.path.join(_project_root(),"database","app.db")

# 获得数据库的连接
def get_connection():
	os.makedirs(os.path.dirname(DB_PATH),exist_ok=True)
	conn = sqlite3.connect(DB_PATH)
	conn.row_factory = sqlite3.Row
	return conn

#初始化数据库表
def init_db():
	_ensure_columns_exist()
	with get_connection() as conn:
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS users(
				id integer PRIMARY KEY AUTOINCREMENT,
				username TEXT NOT NULL UNIQUE,
				password_hash TEXT NOT NULL,
				salt TEXT NOT NULL,
				real_name TEXT DEFAULT '',
				email TEXT DEFAULT '',
				phone TEXT DEFAULT '',
				status INTEGER NOT NULL DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now')),
				update_at TEXT NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS roles(
				id integer PRIMARY KEY AUTOINCREMENT,
				role_name TEXT NOT NULL UNIQUE,
				role_code TEXT NOT NULL UNIQUE,
				description TEXT DEFAULT '',
				status INTEGER NOT NULL DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS permissions(
				id integer PRIMARY KEY AUTOINCREMENT,
				perm_name TEXT NOT NULL,
				perm_code TEXT NOT NULL UNIQUE,
				parent_id INTEGER DEFAULT 0,
				menu_url TEXT DEFAULT '',
				sort_order INTEGER DEFAULT 0,
				create_at TEXT NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS role_permissions(
				id integer PRIMARY KEY AUTOINCREMENT,
				role_id INTEGER NOT NULL,
				permission_id INTEGER NOT NULL,
				FOREIGN KEY(role_id) REFERENCES roles(id),
				FOREIGN KEY(permission_id) REFERENCES permissions(id)
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS user_roles(
				id integer PRIMARY KEY AUTOINCREMENT,
				user_id INTEGER NOT NULL,
				role_id INTEGER NOT NULL,
				FOREIGN KEY(user_id) REFERENCES users(id),
				FOREIGN KEY(role_id) REFERENCES roles(id)
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS admin_sessions(
				id integer PRIMARY KEY AUTOINCREMENT,
				user_id INTEGER NOT NULL,
				login_ip TEXT DEFAULT '',
				login_at TEXT NOT NULL DEFAULT(datetime('now')),
				FOREIGN KEY(user_id) REFERENCES users(id)
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS model_services(
				id integer PRIMARY KEY AUTOINCREMENT,
				model_name TEXT NOT NULL,
				model_code TEXT NOT NULL,
				api_key TEXT NOT NULL,
				base_url TEXT NOT NULL,
				model_id TEXT NOT NULL,
				is_default INTEGER DEFAULT 0,
				status INTEGER DEFAULT 1,
				token_used INTEGER DEFAULT 0,
				create_at TEXT NOT NULL DEFAULT(datetime('now')),
				update_at TEXT NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS watch_sources(
				id integer PRIMARY KEY AUTOINCREMENT,
				source_name TEXT NOT NULL,
				source_code TEXT NOT NULL,
				url_template TEXT NOT NULL,
				headers_json TEXT,
				cookie TEXT,
				status INTEGER DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now')),
				update_at TEXT NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS watch_data(
				id integer PRIMARY KEY AUTOINCREMENT,
				source_id INTEGER NOT NULL,
				keyword TEXT NOT NULL,
				title TEXT,
				content TEXT,
				url TEXT,
				publish_time TEXT,
				create_at TEXT NOT NULL DEFAULT(datetime('now')),
				FOREIGN KEY(source_id) REFERENCES watch_sources(id)
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS api_endpoints(
				id integer PRIMARY KEY AUTOINCREMENT,
				api_name TEXT NOT NULL,
				api_code TEXT NOT NULL UNIQUE,
				api_url TEXT NOT NULL,
				request_method TEXT NOT NULL DEFAULT 'GET',
				response_format TEXT NOT NULL DEFAULT 'JSON',
				qps_limit TEXT DEFAULT '',
				token TEXT DEFAULT '',
				remark TEXT DEFAULT '',
				status INTEGER NOT NULL DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now')),
				update_at TEXT NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS digital_employees(
				id integer PRIMARY KEY AUTOINCREMENT,
				employee_name TEXT NOT NULL,
				employee_code TEXT NOT NULL UNIQUE,
				at_alias TEXT NOT NULL UNIQUE,
				category INTEGER NOT NULL DEFAULT 1,
				service_type TEXT NOT NULL DEFAULT 'LLM',
				description TEXT DEFAULT '',
				model_code TEXT DEFAULT '',
				prompt TEXT DEFAULT '',
				api_code TEXT DEFAULT '',
				config_json TEXT DEFAULT '',
				status INTEGER NOT NULL DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now')),
				update_at TEXT NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS chat_conversations(
				id integer PRIMARY KEY AUTOINCREMENT,
				user_id INTEGER NOT NULL,
				title TEXT DEFAULT '',
				model_service_id INTEGER DEFAULT 0,
				is_pinned INTEGER NOT NULL DEFAULT 0,
				create_at TEXT NOT NULL DEFAULT(datetime('now')),
				update_at TEXT NOT NULL DEFAULT(datetime('now')),
				FOREIGN KEY(user_id) REFERENCES users(id)
			)
			"""
		)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS chat_messages(
				id integer PRIMARY KEY AUTOINCREMENT,
				conversation_id INTEGER NOT NULL,
				role TEXT NOT NULL,
				content TEXT NOT NULL,
				create_at TEXT NOT NULL DEFAULT(datetime('now')),
				FOREIGN KEY(conversation_id) REFERENCES chat_conversations(id)
			)
			"""
		)
		_ensure_chat_conversation_columns_exist(conn)
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS watch_data_detail(
				id integer PRIMARY KEY AUTOINCREMENT,
				data_id INTEGER NOT NULL,
				source_id INTEGER NOT NULL,
				detail_title TEXT,
				detail_content TEXT,
				detail_summary TEXT,
				detail_keywords TEXT,
				source_url TEXT,
				ai_model TEXT,
				tokens_used INTEGER DEFAULT 0,
				deep_status INTEGER DEFAULT 0,
				error_msg TEXT,
				create_at TEXT NOT NULL DEFAULT(datetime('now')),
				FOREIGN KEY(data_id) REFERENCES watch_data(id),
				FOREIGN KEY(source_id) REFERENCES watch_sources(id)
			)
			"""
		)
		init_default_data(conn)

def _ensure_chat_conversation_columns_exist(conn):
	try:
		cursor = conn.execute("PRAGMA table_info(chat_conversations)")
		existing_cols = {row[1] for row in cursor.fetchall()}
		if "is_pinned" not in existing_cols:
			try:
				conn.execute("ALTER TABLE chat_conversations ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0")
				conn.commit()
			except Exception:
				pass
	except Exception:
		pass

def _ensure_columns_exist():
	conn = get_connection()
	try:
		cursor = conn.execute("PRAGMA table_info(users)")
		existing_cols = {row[1] for row in cursor.fetchall()}
		if "real_name" not in existing_cols:
			try:
				conn.execute("ALTER TABLE users ADD COLUMN real_name TEXT DEFAULT ''")
				conn.commit()
			except Exception:
				pass
		if "email" not in existing_cols:
			try:
				conn.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")
				conn.commit()
			except Exception:
				pass
		if "phone" not in existing_cols:
			try:
				conn.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")
				conn.commit()
			except Exception:
				pass
		if "status" not in existing_cols:
			try:
				conn.execute("ALTER TABLE users ADD COLUMN status INTEGER DEFAULT 1")
				conn.commit()
			except Exception:
				pass
		if "update_at" not in existing_cols:
			try:
				conn.execute("ALTER TABLE users ADD COLUMN update_at TEXT")
				conn.execute("UPDATE users SET update_at = datetime('now')")
				conn.commit()
			except Exception:
				pass
	finally:
		conn.close()

def init_default_data(conn):
	cursor = conn.execute("SELECT COUNT(*) FROM roles")
	if cursor.fetchone()[0] == 0:
		conn.execute(
			"INSERT INTO roles(role_name, role_code, description) VALUES(?, ?, ?)",
			("超级管理员", "super_admin", "系统最高权限角色")
		)

	conn.execute(
		"INSERT OR IGNORE INTO roles(role_name, role_code, description) VALUES(?, ?, ?)",
		("超级管理员", "super_admin", "系统最高权限角色")
	)
	conn.execute(
		"INSERT OR IGNORE INTO roles(role_name, role_code, description) VALUES(?, ?, ?)",
		("普通用户", "normal_user", "前端普通用户角色")
	)
	
	cursor = conn.execute("SELECT COUNT(*) FROM watch_sources")
	if cursor.fetchone()[0] == 0:
		headers_json = json.dumps({
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0",
			"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
			"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
			"Connection": "keep-alive",
			"Sec-Fetch-Dest": "document",
			"Sec-Fetch-Mode": "navigate",
			"Sec-Fetch-Site": "same-origin",
			"Upgrade-Insecure-Requests": "1"
		})
		conn.execute(
			"INSERT INTO watch_sources(source_name, source_code, url_template, headers_json, status) VALUES(?, ?, ?, ?, ?)",
			("百度新闻", "baidu_news", "https://www.baidu.com/s?ie=utf-8&bsst=1&rsv_dl=news_b_pn&tn=news&cl=2&medium=0&rtt=1&wd={keyword}&pn={pn}", headers_json, 1)
		)
	cursor = conn.execute("SELECT COUNT(*) FROM api_endpoints")
	if cursor.fetchone()[0] == 0:
		conn.executemany(
			"""
			INSERT INTO api_endpoints(api_name, api_code, api_url, request_method, response_format, qps_limit, token, remark, status)
			VALUES(?,?,?,?,?,?,?,?,?)
			""",
			[
				("网易云随机音乐", "music_wy_rand", "https://api.52vmy.cn/api/music/wy/rand", "GET", "JSON", "每2秒最多4次（携带Token可无视限制）", "", "", 1),
				("三日天气查询", "query_tian", "https://api.52vmy.cn/api/query/tian?city=北京市", "GET", "JSON", "每2秒最多4次（携带Token可无视限制）", "", "点击前往三日天气API", 1),
			]
		)

	def ensure_permission(perm_name: str, perm_code: str, parent_code: str = "", menu_url: str = "", sort_order: int = 0):
		perm_code = (perm_code or "").strip()
		if not perm_code:
			return 0
		row = conn.execute("SELECT id FROM permissions WHERE perm_code=?", (perm_code,)).fetchone()
		if row:
			return row[0]
		parent_id = 0
		parent_code = (parent_code or "").strip()
		if parent_code:
			parent_row = conn.execute("SELECT id FROM permissions WHERE perm_code=?", (parent_code,)).fetchone()
			if not parent_row:
				return 0
			parent_id = parent_row[0]
		try:
			conn.execute(
				"INSERT OR IGNORE INTO permissions(perm_name, perm_code, parent_id, menu_url, sort_order) VALUES(?,?,?,?,?)",
				((perm_name or "").strip(), perm_code, int(parent_id), (menu_url or "").strip(), int(sort_order))
			)
		except Exception:
			return 0
		row = conn.execute("SELECT id FROM permissions WHERE perm_code=?", (perm_code,)).fetchone()
		return row[0] if row else 0

	cursor = conn.execute("SELECT COUNT(*) FROM permissions")
	if cursor.fetchone()[0] == 0:
		permissions = [
			("系统首页", "admin:index", 0, "/admin/index", 1),
			("用户管理", "admin:user:list", 0, "/admin/user/list", 2),
			("新增用户", "admin:user:add", 2, "", 1),
			("编辑用户", "admin:user:edit", 2, "", 2),
			("删除用户", "admin:user:delete", 2, "", 3),
			("角色管理", "admin:role:list", 0, "/admin/role/list", 3),
			("模型引擎", "admin:model:list", 0, "/admin/model/list", 4),
			("瞭望管理", "admin:watch:list", 0, "/admin/watch/list", 5),
			("数据仓库", "admin:warehouse:list", 0, "/admin/warehouse/list", 6),
			("接口管理", "admin:api:list", 0, "/admin/api/list", 7),
			("系统设置", "admin:setting:list", 0, "/admin/setting/list", 8),
			("系统统计", "admin:stats:list", 0, "/admin/stats/list", 9),
		]
		conn.executemany(
			"INSERT INTO permissions(perm_name, perm_code, parent_id, menu_url, sort_order) VALUES(?,?,?,?,?)",
			permissions
		)

	ensure_permission("智能服务", "admin:smart_service", "", "", 10)
	ensure_permission("数字员工", "admin:employee:list", "admin:smart_service", "/admin/employee/list", 1)
	ensure_permission("新增数字员工", "admin:employee:add", "admin:employee:list", "", 1)
	ensure_permission("编辑数字员工", "admin:employee:edit", "admin:employee:list", "", 2)
	ensure_permission("删除数字员工", "admin:employee:delete", "admin:employee:list", "", 3)

	default_employees = [
		("川小农", "chuan_xiao_nong", "川小农", 1, "LLM", "默认模型 + Prompt 的对话型数字员工", "", "你是数字员工“川小农”，以中文简洁、专业地回答用户问题。优先给出结论与可执行建议。", "", json.dumps({"use_default_model": True}, ensure_ascii=False), 1),
		("天气", "weather", "天气", 0, "API", "通过接口管理中的天气API返回天气数据；用户输入为城市名称", "", "", "query_tian", json.dumps({"city_param": "city"}, ensure_ascii=False), 1),
		("音乐", "music", "音乐", 0, "API", "通过接口管理中的随机音乐API返回音乐卡片/数据", "", "", "music_wy_rand", json.dumps({}, ensure_ascii=False), 1),
	]
	for employee_name, employee_code, at_alias, category, service_type, description, model_code, prompt, api_code, config_json, status in default_employees:
		conn.execute(
			"""
			INSERT OR IGNORE INTO digital_employees(employee_name, employee_code, at_alias, category, service_type, description, model_code, prompt, api_code, config_json, status)
			VALUES(?,?,?,?,?,?,?,?,?,?,?)
			""",
			(employee_name, employee_code, at_alias, int(category), service_type, description, model_code, prompt, api_code, config_json, int(status))
		)

	cursor = conn.execute("SELECT id FROM roles WHERE role_code='super_admin'")
	row = cursor.fetchone()
	if row:
		admin_role_id = row[0]
		cursor = conn.execute("SELECT id FROM permissions")
		for perm_row in cursor.fetchall():
			conn.execute(
				"INSERT OR IGNORE INTO role_permissions(role_id, permission_id) VALUES(?,?)",
				(admin_role_id, perm_row[0])
			)
	cursor = conn.execute("SELECT id FROM users WHERE username='admin'")
	admin_user_row = cursor.fetchone()
	if admin_user_row:
		salt = secrets.token_bytes(16)
		password = "admin888"
		dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
		password_hash = dk.hex()
		conn.execute(
			"UPDATE users SET password_hash=?, salt=?, real_name='超级管理员', status=1 WHERE id=?",
			(password_hash, salt.hex(), admin_user_row[0])
		)
		cursor = conn.execute("SELECT id FROM roles WHERE role_code='super_admin'")
		admin_role_row = cursor.fetchone()
		if admin_role_row:
			conn.execute(
				"INSERT OR IGNORE INTO user_roles(user_id, role_id) VALUES(?,?)",
				(admin_user_row[0], admin_role_row[0])
			)
	else:
		salt = secrets.token_bytes(16)
		password = "admin888"
		dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100_000)
		password_hash = dk.hex()
		conn.execute(
			"INSERT INTO users(username, password_hash, salt, real_name, status) VALUES(?,?,?,?,?)",
			("admin", password_hash, salt.hex(), "超级管理员", 1)
		)
		cursor = conn.execute("SELECT id FROM users WHERE username='admin'")
		admin_user_row = cursor.fetchone()
		cursor = conn.execute("SELECT id FROM roles WHERE role_code='super_admin'")
		admin_role_row = cursor.fetchone()
		if admin_user_row and admin_role_row:
			conn.execute(
				"INSERT OR IGNORE INTO user_roles(user_id, role_id) VALUES(?,?)",
				(admin_user_row[0], admin_role_row[0])
			)
