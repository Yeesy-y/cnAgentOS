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
		init_default_data(conn)

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
