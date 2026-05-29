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
		# 用户表
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
		# 角色表
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
		# 权限表
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
		# 角色权限关联表
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
		# 用户角色关联表
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
		# 管理员会话表
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
		# 模型服务表
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
		# 瞭望源表
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
		# 瞭望数据表
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
		# API端点表
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
		# 数字员工表
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
		# AI工具表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS ai_tools(
				id integer PRIMARY KEY AUTOINCREMENT,
				tool_name TEXT NOT NULL,
				tool_code TEXT NOT NULL UNIQUE,
				description TEXT DEFAULT '',
				tool_type TEXT NOT NULL DEFAULT 'function',
				parameters_json TEXT DEFAULT '{}',
				return_schema TEXT DEFAULT '',
				status INTEGER NOT NULL DEFAULT 1,
				create_at TEXT NOT NULL DEFAULT(datetime('now')),
				update_at TEXT NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)
		# 数字员工工具绑定表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS employee_tools(
				id integer PRIMARY KEY AUTOINCREMENT,
				employee_id INTEGER NOT NULL,
				tool_id INTEGER NOT NULL,
				bind_config_json TEXT DEFAULT '{}',
				create_at TEXT NOT NULL DEFAULT(datetime('now')),
				FOREIGN KEY(employee_id) REFERENCES digital_employees(id) ON DELETE CASCADE,
				FOREIGN KEY(tool_id) REFERENCES ai_tools(id) ON DELETE CASCADE,
				UNIQUE(employee_id, tool_id)
			)
			"""
		)
		# 聊天会话表
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
		# 聊天消息表
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
		_ensure_chat_messages_content_type(conn)
		_ensure_chat_conversation_columns_exist(conn)
		# 瞭望数据详情表
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
		
		# ==================== 新增：任务二所需表 ====================
		# 好友关系表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS friends(
				id integer PRIMARY KEY AUTOINCREMENT,
				user_id INTEGER NOT NULL,
				friend_id INTEGER NOT NULL,
				status TEXT DEFAULT 'pending',
				created_at TEXT DEFAULT (datetime('now')),
				FOREIGN KEY(user_id) REFERENCES users(id),
				FOREIGN KEY(friend_id) REFERENCES users(id),
				UNIQUE(user_id, friend_id)
			)
			"""
		)
		_ensure_friends_table_status_exists(conn)
		# 群聊表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS groups(
				id integer PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL,
				creator_id INTEGER NOT NULL,
				created_at TEXT DEFAULT (datetime('now')),
				FOREIGN KEY(creator_id) REFERENCES users(id)
			)
			"""
		)
		# 群成员表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS group_members(
				id integer PRIMARY KEY AUTOINCREMENT,
				group_id INTEGER NOT NULL,
				user_id INTEGER NOT NULL,
				joined_at TEXT DEFAULT (datetime('now')),
				FOREIGN KEY(group_id) REFERENCES groups(id),
				FOREIGN KEY(user_id) REFERENCES users(id),
				UNIQUE(group_id, user_id)
			)
			"""
		)
		# 群数字员工表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS group_employees(
				id integer PRIMARY KEY AUTOINCREMENT,
				group_id INTEGER NOT NULL,
				employee_id INTEGER NOT NULL,
				added_at TEXT DEFAULT (datetime('now')),
				FOREIGN KEY(group_id) REFERENCES groups(id),
				FOREIGN KEY(employee_id) REFERENCES digital_employees(id),
				UNIQUE(group_id, employee_id)
			)
			"""
		)
		# 聊天文件表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS chat_files(
				id integer PRIMARY KEY AUTOINCREMENT,
				original_name TEXT NOT NULL,
				stored_name TEXT NOT NULL,
				file_size INTEGER NOT NULL DEFAULT 0,
				content_type TEXT DEFAULT '',
				file_hash TEXT DEFAULT '',
				uploader_id INTEGER,
				created_at TEXT DEFAULT (datetime('now')),
				FOREIGN KEY(uploader_id) REFERENCES users(id)
			)
			"""
		)
		# 聊天服务器表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS chat_servers(
				id integer PRIMARY KEY AUTOINCREMENT,
				name TEXT NOT NULL,
				host TEXT NOT NULL,
				port INTEGER NOT NULL DEFAULT 9000,
				weight INTEGER NOT NULL DEFAULT 100,
				max_connections INTEGER NOT NULL DEFAULT 1000,
				description TEXT DEFAULT '',
				status TEXT NOT NULL DEFAULT 'active',
				created_at TEXT DEFAULT (datetime('now'))
			)
			"""
		)
		# ==========================================================
		
		# ==================== 新增：聊天消息相关表 ====================
		# 私聊消息表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS private_messages(
				id integer PRIMARY KEY AUTOINCREMENT,
				sender_id INTEGER NOT NULL,
				receiver_id INTEGER NOT NULL,
				content TEXT NOT NULL,
				message_type TEXT DEFAULT 'text',
				is_read INTEGER DEFAULT 0,
				read_at TEXT,
				referenced_message_id INTEGER,
				created_at TEXT DEFAULT (datetime('now')),
				FOREIGN KEY(sender_id) REFERENCES users(id),
				FOREIGN KEY(receiver_id) REFERENCES users(id)
			)
			"""
		)
		# 群聊消息表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS group_messages(
				id integer PRIMARY KEY AUTOINCREMENT,
				group_id INTEGER NOT NULL,
				sender_id INTEGER NOT NULL,
				sender_type TEXT DEFAULT 'user',
				content TEXT NOT NULL,
				message_type TEXT DEFAULT 'text',
				referenced_message_id INTEGER,
				created_at TEXT DEFAULT (datetime('now')),
				FOREIGN KEY(group_id) REFERENCES groups(id)
			)
			"""
		)
		# 群消息已读记录表
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS group_message_reads(
				id integer PRIMARY KEY AUTOINCREMENT,
				message_id INTEGER NOT NULL,
				user_id INTEGER NOT NULL,
				read_at TEXT DEFAULT (datetime('now')),
				FOREIGN KEY(message_id) REFERENCES group_messages(id),
				FOREIGN KEY(user_id) REFERENCES users(id),
				UNIQUE(message_id, user_id)
			)
			"""
		)
		# ==========================================================
		
		init_default_data(conn)

def _ensure_chat_messages_content_type(conn):
	try:
		cursor = conn.execute("PRAGMA table_info(chat_messages)")
		rows = cursor.fetchall()
		for row in rows:
			col_name = row[1]
			col_type = row[2].upper()
			if col_name == "content" and col_type != "TEXT":
				try:
					conn.execute("ALTER TABLE chat_messages RENAME TO chat_messages_old")
					conn.execute("""
						CREATE TABLE chat_messages(
							id integer PRIMARY KEY AUTOINCREMENT,
							conversation_id INTEGER NOT NULL,
							role TEXT NOT NULL,
							content TEXT NOT NULL,
							create_at TEXT NOT NULL DEFAULT(datetime('now')),
							FOREIGN KEY(conversation_id) REFERENCES chat_conversations(id)
						)
					""")
					conn.execute("""
						INSERT INTO chat_messages(id, conversation_id, role, content, create_at)
						SELECT id, conversation_id, role, content, create_at FROM chat_messages_old
					""")
					conn.execute("DROP TABLE chat_messages_old")
					conn.commit()
				except Exception as e:
					try:
						conn.execute("ALTER TABLE chat_messages_old RENAME TO chat_messages")
					except:
						pass
				break
	except Exception:
		pass

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

def _ensure_friends_table_status_exists(conn):
	try:
		cursor = conn.execute("PRAGMA table_info(friends)")
		existing_cols = {row[1] for row in cursor.fetchall()}
		if "status" not in existing_cols:
			try:
				conn.execute("ALTER TABLE friends ADD COLUMN status TEXT DEFAULT 'pending'")
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
	conn.execute(
		"""
		INSERT OR IGNORE INTO api_endpoints(api_name, api_code, api_url, request_method, response_format, qps_limit, token, remark, status)
		VALUES(?,?,?,?,?,?,?,?,?)
		""",
		("毒鸡汤", "wl_yan_du", "https://api.52vmy.cn/api/wl/yan/du", "GET", "JSON", "每2秒最多4次（携带Token可无视限制）", "", "请求示例：/api/wl/yan/du?type=text", 1)
	)

	cursor = conn.execute("SELECT COUNT(*) FROM ai_tools")
	if cursor.fetchone()[0] == 0:
		conn.executemany(
			"""
			INSERT OR IGNORE INTO ai_tools(tool_name, tool_code, description, tool_type, parameters_json, return_schema, status)
			VALUES(?,?,?,?,?,?,?)
			""",
			[
				("接口调用", "tool_call_api", "通过接口管理调用已配置的API端点", "function",
				 json.dumps({
					 "type": "object",
					 "properties": {
						 "api_code": {"type": "string", "description": "接口编码（接口管理中的api_code）"},
						 "params": {"type": "object", "description": "请求参数对象"},
						 "timeout": {"type": "integer", "description": "超时时间（秒）", "default": 30}
					 },
					 "required": ["api_code"]
				 }, ensure_ascii=False),
				 json.dumps({"type": "object"}, ensure_ascii=False),
				 1),
				("天气查询", "tool_weather_query", "查询指定城市天气（默认使用三日天气查询接口）", "function",
				 json.dumps({
					 "type": "object",
					 "properties": {"city": {"type": "string", "description": "城市名称，如：北京市"}},
					 "required": ["city"]
				 }, ensure_ascii=False),
				 json.dumps({"type": "object"}, ensure_ascii=False),
				 1),
				("随机音乐", "tool_music_random", "随机获取网易云音乐推荐", "function",
				 json.dumps({"type": "object", "properties": {}}, ensure_ascii=False),
				 json.dumps({"type": "object"}, ensure_ascii=False),
				 1),
				("毒鸡汤", "tool_poison_soup", "随机获取毒鸡汤语句", "function",
				 json.dumps({"type": "object", "properties": {}}, ensure_ascii=False),
				 json.dumps({"type": "object"}, ensure_ascii=False),
				 1),
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
		("川农小助手", "chuan_nong_xiao_zhu_shou", "川农小助手", 1, "LLM", 
		 "负责关于川农的限定范围问题聊天，支持多轮对话", "", 
		 "你是四川农业大学的专属数字员工助手——川农小助手。你的任务是回答与四川农业大学（川农）相关的问题，包括但不限于：\n1. 学校历史、校区分布、院系设置\n2. 招生信息、专业介绍、录取分数线\n3. 校园生活、住宿条件、食堂美食\n4. 师资力量、科研成果、学术交流\n5. 校园活动、社团组织、体育赛事\n6. 校园设施、图书馆、实验室等\n\n回答要求：\n- 仅回答与川农相关的问题\n- 如用户问题超出范围，礼貌说明你主要专注于川农相关问题\n- 保持专业、友好、耐心的态度\n- 支持多轮对话，记住之前的上下文\n- 提供准确、实用的信息", 
		 "", json.dumps({"use_default_model": True}, ensure_ascii=False), 1),
		("天气小助手", "weather", "天气小助手", 0, "API", 
		 "输入城市名，返回指定城市天气卡片+动态联动的天气特效", "", 
		 "", "query_tian", json.dumps({"city_param": "city"}, ensure_ascii=False), 1),
		("毒鸡汤助手", "poison_chicken_soup", "毒鸡汤助手", 0, "API", 
		 "随机回复毒鸡汤语句", "", "", "", json.dumps({}, ensure_ascii=False), 1),
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
