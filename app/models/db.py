# 数据库链接与建表
import os
import sqlite3
import hashlib
import secrets
import json
import threading
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

# 获得项目根路径的方法
def _project_root():
	return os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir,os.pardir))

_DB_CONFIG_PATH = os.path.join(_project_root(), "database", "db_config.json")
_db_config_lock = threading.RLock()

def _default_db_config() -> Dict[str, Any]:
	return {
		"db_type": "sqlite",
		"sqlite": {
			"path": "database/app.db"
		},
		"mysql": {
			"host": "127.0.0.1",
			"port": 3306,
			"user": "root",
			"password": "",
			"database": "cnAgentOS",
			"charset": "utf8mb4"
		}
	}

def load_db_config() -> Dict[str, Any]:
	with _db_config_lock:
		try:
			if not os.path.exists(_DB_CONFIG_PATH):
				return _default_db_config()
			with open(_DB_CONFIG_PATH, "r", encoding="utf-8") as f:
				data = json.load(f)
			if not isinstance(data, dict):
				return _default_db_config()
			cfg = _default_db_config()
			cfg.update({k: v for k, v in data.items() if k in ("db_type", "sqlite", "mysql")})
			if not isinstance(cfg.get("sqlite"), dict):
				cfg["sqlite"] = _default_db_config()["sqlite"]
			if not isinstance(cfg.get("mysql"), dict):
				cfg["mysql"] = _default_db_config()["mysql"]
			cfg["db_type"] = (cfg.get("db_type") or "sqlite").strip().lower()
			if cfg["db_type"] not in ("sqlite", "mysql"):
				cfg["db_type"] = "sqlite"
			return cfg
		except Exception:
			return _default_db_config()

def save_db_config(cfg: Dict[str, Any]) -> None:
	with _db_config_lock:
		os.makedirs(os.path.dirname(_DB_CONFIG_PATH), exist_ok=True)
		with open(_DB_CONFIG_PATH, "w", encoding="utf-8") as f:
			json.dump(cfg, f, ensure_ascii=False, indent=2)

def get_db_type() -> str:
	return load_db_config().get("db_type", "sqlite")

def set_db_type(db_type: str) -> None:
	db_type = (db_type or "").strip().lower()
	if db_type not in ("sqlite", "mysql"):
		db_type = "sqlite"
	cfg = load_db_config()
	cfg["db_type"] = db_type
	save_db_config(cfg)

def _resolve_sqlite_path(sqlite_cfg: Dict[str, Any]) -> str:
	p = (sqlite_cfg or {}).get("path") or "database/app.db"
	if os.path.isabs(p):
		return p
	return os.path.join(_project_root(), p)

DB_PATH = _resolve_sqlite_path(load_db_config().get("sqlite", {}))

class CompatRow:
	def __init__(self, columns: Sequence[str], values: Sequence[Any]):
		self._columns = list(columns)
		self._values = list(values)
		self._map = {self._columns[i]: self._values[i] for i in range(min(len(self._columns), len(self._values)))}

	def keys(self):
		return self._map.keys()

	def get(self, key: str, default: Any = None) -> Any:
		return self._map.get(key, default)

	def __getitem__(self, key: Union[int, str]) -> Any:
		if isinstance(key, int):
			return self._values[key]
		return self._map[key]

	def __iter__(self):
		return iter(self._values)

	def __len__(self):
		return len(self._values)

def _sqlite_row_factory(cursor: sqlite3.Cursor, row: sqlite3.Row) -> CompatRow:
	cols = [d[0] for d in (cursor.description or [])]
	return CompatRow(cols, row)

def _mysql_replace_qmark(sql: str) -> str:
	out: List[str] = []
	in_single = False
	in_double = False
	escaped = False
	for ch in sql:
		if escaped:
			out.append(ch)
			escaped = False
			continue
		if ch == "\\":
			out.append(ch)
			escaped = True
			continue
		if ch == "'" and not in_double:
			in_single = not in_single
			out.append(ch)
			continue
		if ch == '"' and not in_single:
			in_double = not in_double
			out.append(ch)
			continue
		if ch == "?" and not in_single and not in_double:
			out.append("%s")
		else:
			out.append(ch)
	return "".join(out)

def _translate_sql_for_mysql(sql: str) -> str:
	s = sql
	s = s.replace("datetime('now')", "NOW()")
	s = s.replace("DEFAULT(datetime('now'))", "DEFAULT CURRENT_TIMESTAMP")
	s = s.replace("DEFAULT (datetime('now'))", "DEFAULT CURRENT_TIMESTAMP")
	s = s.replace("INSERT OR IGNORE", "INSERT IGNORE")
	s = s.replace("insert or ignore", "INSERT IGNORE")
	s = s.replace("AUTOINCREMENT", "AUTO_INCREMENT")
	s = _mysql_replace_qmark(s)
	return _quote_mysql_reserved(s)

def _quote_mysql_reserved(sql: str) -> str:
	out: List[str] = []
	token = []
	in_single = False
	in_double = False
	in_backtick = False
	escaped = False
	def flush_token():
		nonlocal token
		if not token:
			return
		word = "".join(token)
		lw = word.lower()
		if lw == "groups":
			out.append("`groups`")
		else:
			out.append(word)
		token = []
	for ch in sql:
		if escaped:
			if token:
				token.append(ch)
			else:
				out.append(ch)
			escaped = False
			continue
		if ch == "\\":
			if token:
				token.append(ch)
			else:
				out.append(ch)
			escaped = True
			continue
		if ch == "'" and not in_double and not in_backtick:
			flush_token()
			in_single = not in_single
			out.append(ch)
			continue
		if ch == '"' and not in_single and not in_backtick:
			flush_token()
			in_double = not in_double
			out.append(ch)
			continue
		if ch == "`" and not in_single and not in_double:
			flush_token()
			in_backtick = not in_backtick
			out.append(ch)
			continue
		if in_single or in_double or in_backtick:
			out.append(ch)
			continue
		if ch.isalnum() or ch == "_":
			token.append(ch)
		else:
			flush_token()
			out.append(ch)
	flush_token()
	return "".join(out)

class _VirtualCursor:
	def __init__(self, columns: Sequence[str], rows: Sequence[Sequence[Any]]):
		self.description = [(c, None, None, None, None, None, None) for c in columns]
		self._rows = [CompatRow(columns, r) for r in rows]
		self._idx = 0

	def fetchone(self):
		if self._idx >= len(self._rows):
			return None
		row = self._rows[self._idx]
		self._idx += 1
		return row

	def fetchall(self):
		if self._idx >= len(self._rows):
			return []
		rows = self._rows[self._idx:]
		self._idx = len(self._rows)
		return rows

class _MySQLCursorWrapper:
	def __init__(self, cursor):
		self._cursor = cursor
		self.description = None

	def execute(self, sql: str, params: Optional[Sequence[Any]] = None):
		self._cursor.execute(sql, tuple(params or ()))
		self.description = self._cursor.description
		return self

	def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any]]):
		self._cursor.executemany(sql, [tuple(p) for p in seq_of_params])
		self.description = self._cursor.description
		return self

	def fetchone(self):
		row = self._cursor.fetchone()
		if row is None:
			return None
		cols = [d[0] for d in (self.description or [])]
		return CompatRow(cols, row)

	def fetchall(self):
		rows = self._cursor.fetchall() or []
		cols = [d[0] for d in (self.description or [])]
		return [CompatRow(cols, r) for r in rows]

	@property
	def lastrowid(self):
		return getattr(self._cursor, "lastrowid", None)

class _DBConnection:
	def __init__(self, db_type: str, conn, mysql_database: str = ""):
		self._db_type = db_type
		self._conn = conn
		self._mysql_database = mysql_database

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc, tb):
		try:
			if exc_type is None:
				try:
					self.commit()
				except Exception:
					pass
		finally:
			self.close()
		return False

	def close(self):
		try:
			self._conn.close()
		except Exception:
			pass

	def commit(self):
		return self._conn.commit()

	def cursor(self):
		if self._db_type == "mysql":
			return _MySQLCursorWrapper(self._conn.cursor())
		return self._conn.cursor()

	def execute(self, sql: str, params: Optional[Sequence[Any]] = None):
		if self._db_type != "mysql":
			return self._conn.execute(sql, tuple(params or ()))
		virtual = self._handle_mysql_virtual(sql, params)
		if virtual is not None:
			return virtual
		cur = _MySQLCursorWrapper(self._conn.cursor())
		cur.execute(_translate_sql_for_mysql(sql), params)
		return cur

	def executemany(self, sql: str, seq_of_params: Iterable[Sequence[Any]]):
		if self._db_type != "mysql":
			return self._conn.executemany(sql, list(seq_of_params))
		cur = _MySQLCursorWrapper(self._conn.cursor())
		cur.executemany(_translate_sql_for_mysql(sql), seq_of_params)
		return cur

	def _handle_mysql_virtual(self, sql: str, params: Optional[Sequence[Any]]):
		s = (sql or "").strip()
		low = s.lower()
		if low.startswith("pragma table_info(") and s.endswith(")"):
			table = s[len("PRAGMA table_info("):-1].strip().strip("`").strip('"').strip("'")
			return self._mysql_pragma_table_info(table)
		if low.startswith("pragma index_list(") and s.endswith(")"):
			table = s[len("PRAGMA index_list("):-1].strip().strip("`").strip('"').strip("'")
			return self._mysql_pragma_index_list(table)
		if low.startswith("pragma index_info(") and s.endswith(")"):
			index_name = s[len("PRAGMA index_info("):-1].strip().strip("`").strip('"').strip("'")
			return self._mysql_pragma_index_info(index_name)
		return None

	def _mysql_pragma_table_info(self, table: str):
		q = """
			SELECT COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_KEY
			FROM information_schema.COLUMNS
			WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s
			ORDER BY ORDINAL_POSITION
		"""
		cur = self._conn.cursor()
		cur.execute(q, (self._mysql_database, table))
		rows = cur.fetchall() or []
		out_rows = []
		for i, (name, col_type, is_nullable, default, col_key) in enumerate(rows):
			notnull = 1 if str(is_nullable).upper() == "NO" else 0
			pk = 1 if str(col_key).upper() == "PRI" else 0
			out_rows.append((i, name, col_type, notnull, default, pk))
		return _VirtualCursor(["cid", "name", "type", "notnull", "dflt_value", "pk"], out_rows)

	def _mysql_pragma_index_list(self, table: str):
		q = "SHOW INDEX FROM " + _quote_mysql_reserved(table)
		cur = self._conn.cursor()
		cur.execute(q)
		rows = cur.fetchall() or []
		by_name: Dict[str, Dict[str, Any]] = {}
		for r in rows:
			key_name = r[2]
			non_unique = r[1]
			if key_name not in by_name:
				by_name[key_name] = {
					"name": key_name,
					"unique": 0 if int(non_unique) == 1 else 1,
					"origin": "pk" if str(key_name).upper() == "PRIMARY" else "c",
				}
		out_rows = []
		for seq, name in enumerate(sorted(by_name.keys())):
			info = by_name[name]
			out_rows.append((seq, info["name"], info["unique"], info["origin"], 0))
		return _VirtualCursor(["seq", "name", "unique", "origin", "partial"], out_rows)

	def _mysql_pragma_index_info(self, index_name: str):
		q = """
			SELECT SEQ_IN_INDEX, COLUMN_NAME
			FROM information_schema.STATISTICS
			WHERE TABLE_SCHEMA=%s AND INDEX_NAME=%s
			ORDER BY SEQ_IN_INDEX
		"""
		cur = self._conn.cursor()
		cur.execute(q, (self._mysql_database, index_name))
		rows = cur.fetchall() or []
		out_rows = []
		for seq_in_index, col_name in rows:
			out_rows.append((int(seq_in_index) - 1, 0, col_name))
		return _VirtualCursor(["seqno", "cid", "name"], out_rows)

def _import_mysql_driver():
	try:
		import importlib
		pymysql = importlib.import_module("pymysql")
		return "pymysql", pymysql
	except Exception:
		pass
	try:
		import importlib
		mysql_connector = importlib.import_module("mysql.connector")
		return "mysql.connector", mysql_connector
	except Exception:
		return "", None

def mysql_driver_available() -> bool:
	name, mod = _import_mysql_driver()
	return bool(name and mod)

def test_mysql_connection(mysql_cfg: Dict[str, Any]) -> Tuple[bool, str]:
	mysql_cfg = mysql_cfg or {}
	mysql_host = (mysql_cfg.get("host") or "127.0.0.1").strip()
	mysql_port = int(mysql_cfg.get("port") or 3306)
	mysql_user = (mysql_cfg.get("user") or "").strip()
	mysql_password = mysql_cfg.get("password") or ""
	mysql_database = (mysql_cfg.get("database") or "").strip()
	mysql_charset = (mysql_cfg.get("charset") or "utf8mb4").strip() or "utf8mb4"

	driver_name, driver_mod = _import_mysql_driver()
	if not driver_mod:
		return False, "未安装 MySQL 驱动，请安装 pymysql 或 mysql-connector-python"
	if not mysql_database:
		return False, "mysql_database 不能为空"

	def _connect(database: Optional[str]):
		kwargs = dict(
			host=mysql_host,
			port=mysql_port,
			user=mysql_user,
			password=mysql_password,
			charset=mysql_charset,
			autocommit=False,
		)
		if database:
			kwargs["database"] = database
		return driver_mod.connect(**kwargs)

	def _err_code(ex: Exception) -> int:
		try:
			if hasattr(ex, "args") and ex.args and isinstance(ex.args[0], int):
				return int(ex.args[0])
		except Exception:
			return 0
		return 0

	try:
		conn = _connect(mysql_database)
		try:
			cur = conn.cursor()
			cur.execute("SELECT 1")
			cur.fetchone()
		finally:
			try:
				conn.close()
			except Exception:
				pass
		return True, "ok"
	except Exception as e:
		code = _err_code(e)
		if code == 2003:
			return False, f"无法连接 MySQL：{mysql_host}:{mysql_port}（请确认 MySQL 已启动且端口正确）"
		if code == 1045:
			return False, f"MySQL 认证失败：账号/密码错误或无权限（{mysql_user}@{mysql_host}:{mysql_port}）"
		if code == 1049:
			try:
				conn2 = _connect(None)
				try:
					cur2 = conn2.cursor()
					cur2.execute(f"CREATE DATABASE IF NOT EXISTS `{mysql_database}` DEFAULT CHARACTER SET {mysql_charset}")
					conn2.commit()
				finally:
					try:
						conn2.close()
					except Exception:
						pass
				conn3 = _connect(mysql_database)
				try:
					cur3 = conn3.cursor()
					cur3.execute("SELECT 1")
					cur3.fetchone()
				finally:
					try:
						conn3.close()
					except Exception:
						pass
				return True, f"已自动创建数据库：{mysql_database}"
			except Exception as e2:
				return False, f"数据库不存在且自动创建失败：{mysql_database}（{type(e2).__name__}: {str(e2)}）"
		return False, f"MySQL 连接失败：{type(e).__name__}: {str(e)}"

# 获得数据库的连接
def get_connection():
	cfg = load_db_config()
	db_type = (cfg.get("db_type") or "sqlite").strip().lower()
	if db_type != "mysql":
		sqlite_path = _resolve_sqlite_path(cfg.get("sqlite", {}))
		os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
		conn = sqlite3.connect(sqlite_path)
		conn.row_factory = _sqlite_row_factory
		return _DBConnection("sqlite", conn)

	mysql_cfg = cfg.get("mysql", {}) or {}
	mysql_host = (mysql_cfg.get("host") or "127.0.0.1").strip()
	mysql_port = int(mysql_cfg.get("port") or 3306)
	mysql_user = (mysql_cfg.get("user") or "").strip()
	mysql_password = mysql_cfg.get("password") or ""
	mysql_database = (mysql_cfg.get("database") or "").strip()
	mysql_charset = (mysql_cfg.get("charset") or "utf8mb4").strip() or "utf8mb4"

	driver_name, driver_mod = _import_mysql_driver()
	if not driver_mod:
		try:
			cfg["db_type"] = "sqlite"
			save_db_config(cfg)
		except Exception:
			pass
		sqlite_path = _resolve_sqlite_path(cfg.get("sqlite", {}))
		os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
		conn = sqlite3.connect(sqlite_path)
		conn.row_factory = _sqlite_row_factory
		return _DBConnection("sqlite", conn)

	try:
		conn = driver_mod.connect(
			host=mysql_host,
			port=mysql_port,
			user=mysql_user,
			password=mysql_password,
			database=mysql_database,
			charset=mysql_charset,
			autocommit=False,
		)
		return _DBConnection("mysql", conn, mysql_database=mysql_database)
	except Exception as e:
		raise RuntimeError(f"MySQL connection failed: {type(e).__name__}: {str(e)}") from e

#初始化数据库表
def init_db():
	with get_connection() as conn:
		_ensure_columns_exist(conn)
		if get_db_type() == "mysql":
			_init_mysql_schema(conn)
		else:
			_init_sqlite_schema(conn)
		_ensure_chat_messages_content_type(conn)
		_ensure_chat_conversation_columns_exist(conn)
		_ensure_friends_table_status_exists(conn)
		init_default_data(conn)

def _init_sqlite_schema(conn):
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
	conn.execute(
		"""
		CREATE TABLE IF NOT EXISTS employee_private_messages(
			id integer PRIMARY KEY AUTOINCREMENT,
			user_id INTEGER NOT NULL,
			employee_id INTEGER NOT NULL,
			sender_type TEXT NOT NULL DEFAULT 'user',
			content TEXT NOT NULL,
			message_type TEXT DEFAULT 'text',
			is_read INTEGER DEFAULT 0,
			read_at TEXT,
			referenced_message_id INTEGER,
			created_at TEXT DEFAULT (datetime('now')),
			FOREIGN KEY(user_id) REFERENCES users(id),
			FOREIGN KEY(employee_id) REFERENCES digital_employees(id)
		)
		"""
	)
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
	conn.execute(
		"""
		CREATE TABLE IF NOT EXISTS risk_records(
			id integer PRIMARY KEY AUTOINCREMENT,
			username TEXT NOT NULL DEFAULT '',
			user_id INTEGER DEFAULT 0,
			risk_level TEXT NOT NULL,
			source_type TEXT NOT NULL,
			source_name TEXT DEFAULT '',
			risk_keywords TEXT DEFAULT '[]',
			keyword_count INTEGER DEFAULT 0,
			risk_score INTEGER DEFAULT 0,
			content_preview TEXT DEFAULT '',
			ref_id INTEGER DEFAULT 0,
			create_at TEXT NOT NULL DEFAULT(datetime('now')),
			UNIQUE(source_type, ref_id)
		)
		"""
	)

def _init_mysql_schema(conn):
	stmts = [
		"""
		CREATE TABLE IF NOT EXISTS users(
			id INT AUTO_INCREMENT PRIMARY KEY,
			username VARCHAR(255) NOT NULL,
			password_hash TEXT NOT NULL,
			salt VARCHAR(255) NOT NULL,
			real_name VARCHAR(255) DEFAULT '',
			email VARCHAR(255) DEFAULT '',
			phone VARCHAR(255) DEFAULT '',
			status INT NOT NULL DEFAULT 1,
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			update_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
			UNIQUE KEY uq_users_username(username)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS roles(
			id INT AUTO_INCREMENT PRIMARY KEY,
			role_name VARCHAR(255) NOT NULL,
			role_code VARCHAR(255) NOT NULL,
			description TEXT,
			status INT NOT NULL DEFAULT 1,
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			UNIQUE KEY uq_roles_role_name(role_name),
			UNIQUE KEY uq_roles_role_code(role_code)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS permissions(
			id INT AUTO_INCREMENT PRIMARY KEY,
			perm_name VARCHAR(255) NOT NULL,
			perm_code VARCHAR(255) NOT NULL,
			parent_id INT DEFAULT 0,
			menu_url VARCHAR(1024) DEFAULT '',
			sort_order INT DEFAULT 0,
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			UNIQUE KEY uq_permissions_perm_code(perm_code)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS role_permissions(
			id INT AUTO_INCREMENT PRIMARY KEY,
			role_id INT NOT NULL,
			permission_id INT NOT NULL,
			KEY idx_role_permissions_role(role_id),
			KEY idx_role_permissions_perm(permission_id),
			CONSTRAINT fk_role_permissions_role FOREIGN KEY(role_id) REFERENCES roles(id),
			CONSTRAINT fk_role_permissions_perm FOREIGN KEY(permission_id) REFERENCES permissions(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS user_roles(
			id INT AUTO_INCREMENT PRIMARY KEY,
			user_id INT NOT NULL,
			role_id INT NOT NULL,
			KEY idx_user_roles_user(user_id),
			KEY idx_user_roles_role(role_id),
			CONSTRAINT fk_user_roles_user FOREIGN KEY(user_id) REFERENCES users(id),
			CONSTRAINT fk_user_roles_role FOREIGN KEY(role_id) REFERENCES roles(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS admin_sessions(
			id INT AUTO_INCREMENT PRIMARY KEY,
			user_id INT NOT NULL,
			login_ip VARCHAR(255) DEFAULT '',
			login_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			KEY idx_admin_sessions_user(user_id),
			CONSTRAINT fk_admin_sessions_user FOREIGN KEY(user_id) REFERENCES users(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS model_services(
			id INT AUTO_INCREMENT PRIMARY KEY,
			model_name VARCHAR(255) NOT NULL,
			model_code VARCHAR(255) NOT NULL,
			api_key TEXT NOT NULL,
			base_url VARCHAR(1024) NOT NULL,
			model_id VARCHAR(255) NOT NULL,
			is_default INT DEFAULT 0,
			status INT DEFAULT 1,
			token_used INT DEFAULT 0,
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			update_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS watch_sources(
			id INT AUTO_INCREMENT PRIMARY KEY,
			source_name VARCHAR(255) NOT NULL,
			source_code VARCHAR(255) NOT NULL,
			url_template TEXT NOT NULL,
			headers_json TEXT,
			cookie TEXT,
			status INT DEFAULT 1,
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			update_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS watch_data(
			id INT AUTO_INCREMENT PRIMARY KEY,
			source_id INT NOT NULL,
			keyword VARCHAR(255) NOT NULL,
			title TEXT,
			content TEXT,
			url TEXT,
			publish_time VARCHAR(255),
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			KEY idx_watch_data_source(source_id),
			CONSTRAINT fk_watch_data_source FOREIGN KEY(source_id) REFERENCES watch_sources(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS api_endpoints(
			id INT AUTO_INCREMENT PRIMARY KEY,
			api_name VARCHAR(255) NOT NULL,
			api_code VARCHAR(255) NOT NULL,
			api_url TEXT NOT NULL,
			request_method VARCHAR(16) NOT NULL DEFAULT 'GET',
			response_format VARCHAR(32) NOT NULL DEFAULT 'JSON',
			qps_limit VARCHAR(255) DEFAULT '',
			token VARCHAR(255) DEFAULT '',
			remark TEXT,
			status INT NOT NULL DEFAULT 1,
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			update_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
			UNIQUE KEY uq_api_endpoints_api_code(api_code)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS digital_employees(
			id INT AUTO_INCREMENT PRIMARY KEY,
			employee_name VARCHAR(255) NOT NULL,
			employee_code VARCHAR(255) NOT NULL,
			at_alias VARCHAR(255) NOT NULL,
			category INT NOT NULL DEFAULT 1,
			service_type VARCHAR(32) NOT NULL DEFAULT 'LLM',
			description TEXT,
			model_code VARCHAR(255) DEFAULT '',
			prompt TEXT,
			api_code VARCHAR(255) DEFAULT '',
			config_json TEXT,
			status INT NOT NULL DEFAULT 1,
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			update_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
			UNIQUE KEY uq_digital_employees_employee_code(employee_code),
			UNIQUE KEY uq_digital_employees_at_alias(at_alias)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS ai_tools(
			id INT AUTO_INCREMENT PRIMARY KEY,
			tool_name VARCHAR(255) NOT NULL,
			tool_code VARCHAR(255) NOT NULL,
			description TEXT,
			tool_type VARCHAR(64) NOT NULL DEFAULT 'function',
			parameters_json TEXT,
			return_schema TEXT,
			status INT NOT NULL DEFAULT 1,
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			update_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
			UNIQUE KEY uq_ai_tools_tool_code(tool_code)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS employee_tools(
			id INT AUTO_INCREMENT PRIMARY KEY,
			employee_id INT NOT NULL,
			tool_id INT NOT NULL,
			bind_config_json TEXT,
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			UNIQUE KEY uq_employee_tools_pair(employee_id, tool_id),
			KEY idx_employee_tools_employee(employee_id),
			KEY idx_employee_tools_tool(tool_id),
			CONSTRAINT fk_employee_tools_employee FOREIGN KEY(employee_id) REFERENCES digital_employees(id) ON DELETE CASCADE,
			CONSTRAINT fk_employee_tools_tool FOREIGN KEY(tool_id) REFERENCES ai_tools(id) ON DELETE CASCADE
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS chat_conversations(
			id INT AUTO_INCREMENT PRIMARY KEY,
			user_id INT NOT NULL,
			title VARCHAR(255) DEFAULT '',
			model_service_id INT DEFAULT 0,
			is_pinned INT NOT NULL DEFAULT 0,
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			update_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
			KEY idx_chat_conversations_user(user_id),
			CONSTRAINT fk_chat_conversations_user FOREIGN KEY(user_id) REFERENCES users(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS chat_messages(
			id INT AUTO_INCREMENT PRIMARY KEY,
			conversation_id INT NOT NULL,
			role VARCHAR(64) NOT NULL,
			content TEXT NOT NULL,
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			KEY idx_chat_messages_conversation(conversation_id),
			CONSTRAINT fk_chat_messages_conversation FOREIGN KEY(conversation_id) REFERENCES chat_conversations(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS watch_data_detail(
			id INT AUTO_INCREMENT PRIMARY KEY,
			data_id INT NOT NULL,
			source_id INT NOT NULL,
			detail_title TEXT,
			detail_content TEXT,
			detail_summary TEXT,
			detail_keywords TEXT,
			source_url TEXT,
			ai_model VARCHAR(255),
			tokens_used INT DEFAULT 0,
			deep_status INT DEFAULT 0,
			error_msg TEXT,
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			KEY idx_watch_data_detail_data(data_id),
			KEY idx_watch_data_detail_source(source_id),
			CONSTRAINT fk_watch_data_detail_data FOREIGN KEY(data_id) REFERENCES watch_data(id),
			CONSTRAINT fk_watch_data_detail_source FOREIGN KEY(source_id) REFERENCES watch_sources(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS friends(
			id INT AUTO_INCREMENT PRIMARY KEY,
			user_id INT NOT NULL,
			friend_id INT NOT NULL,
			status VARCHAR(32) DEFAULT 'pending',
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			UNIQUE KEY uq_friends_pair(user_id, friend_id),
			KEY idx_friends_user(user_id),
			KEY idx_friends_friend(friend_id),
			CONSTRAINT fk_friends_user FOREIGN KEY(user_id) REFERENCES users(id),
			CONSTRAINT fk_friends_friend FOREIGN KEY(friend_id) REFERENCES users(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS `groups`(
			id INT AUTO_INCREMENT PRIMARY KEY,
			name VARCHAR(255) NOT NULL,
			creator_id INT NOT NULL,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			KEY idx_groups_creator(creator_id),
			CONSTRAINT fk_groups_creator FOREIGN KEY(creator_id) REFERENCES users(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS group_members(
			id INT AUTO_INCREMENT PRIMARY KEY,
			group_id INT NOT NULL,
			user_id INT NOT NULL,
			joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			UNIQUE KEY uq_group_members_pair(group_id, user_id),
			KEY idx_group_members_group(group_id),
			KEY idx_group_members_user(user_id),
			CONSTRAINT fk_group_members_group FOREIGN KEY(group_id) REFERENCES `groups`(id),
			CONSTRAINT fk_group_members_user FOREIGN KEY(user_id) REFERENCES users(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS group_employees(
			id INT AUTO_INCREMENT PRIMARY KEY,
			group_id INT NOT NULL,
			employee_id INT NOT NULL,
			added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			UNIQUE KEY uq_group_employees_pair(group_id, employee_id),
			KEY idx_group_employees_group(group_id),
			KEY idx_group_employees_employee(employee_id),
			CONSTRAINT fk_group_employees_group FOREIGN KEY(group_id) REFERENCES `groups`(id),
			CONSTRAINT fk_group_employees_employee FOREIGN KEY(employee_id) REFERENCES digital_employees(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS chat_files(
			id INT AUTO_INCREMENT PRIMARY KEY,
			original_name TEXT NOT NULL,
			stored_name TEXT NOT NULL,
			file_size INT NOT NULL DEFAULT 0,
			content_type VARCHAR(255) DEFAULT '',
			file_hash VARCHAR(255) DEFAULT '',
			uploader_id INT,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			KEY idx_chat_files_uploader(uploader_id),
			CONSTRAINT fk_chat_files_uploader FOREIGN KEY(uploader_id) REFERENCES users(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS chat_servers(
			id INT AUTO_INCREMENT PRIMARY KEY,
			name VARCHAR(255) NOT NULL,
			host VARCHAR(255) NOT NULL,
			port INT NOT NULL DEFAULT 9000,
			weight INT NOT NULL DEFAULT 100,
			max_connections INT NOT NULL DEFAULT 1000,
			description TEXT,
			status VARCHAR(32) NOT NULL DEFAULT 'active',
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS private_messages(
			id INT AUTO_INCREMENT PRIMARY KEY,
			sender_id INT NOT NULL,
			receiver_id INT NOT NULL,
			content TEXT NOT NULL,
			message_type VARCHAR(32) DEFAULT 'text',
			is_read INT DEFAULT 0,
			read_at DATETIME,
			referenced_message_id INT,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			KEY idx_private_messages_sender(sender_id),
			KEY idx_private_messages_receiver(receiver_id),
			CONSTRAINT fk_private_messages_sender FOREIGN KEY(sender_id) REFERENCES users(id),
			CONSTRAINT fk_private_messages_receiver FOREIGN KEY(receiver_id) REFERENCES users(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS employee_private_messages(
			id INT AUTO_INCREMENT PRIMARY KEY,
			user_id INT NOT NULL,
			employee_id INT NOT NULL,
			sender_type VARCHAR(32) NOT NULL DEFAULT 'user',
			content TEXT NOT NULL,
			message_type VARCHAR(32) DEFAULT 'text',
			is_read INT DEFAULT 0,
			read_at DATETIME,
			referenced_message_id INT,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			KEY idx_employee_private_messages_user(user_id),
			KEY idx_employee_private_messages_employee(employee_id),
			CONSTRAINT fk_employee_private_messages_user FOREIGN KEY(user_id) REFERENCES users(id),
			CONSTRAINT fk_employee_private_messages_employee FOREIGN KEY(employee_id) REFERENCES digital_employees(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS group_messages(
			id INT AUTO_INCREMENT PRIMARY KEY,
			group_id INT NOT NULL,
			sender_id INT NOT NULL,
			sender_type VARCHAR(32) DEFAULT 'user',
			content TEXT NOT NULL,
			message_type VARCHAR(32) DEFAULT 'text',
			referenced_message_id INT,
			created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			KEY idx_group_messages_group(group_id),
			CONSTRAINT fk_group_messages_group FOREIGN KEY(group_id) REFERENCES `groups`(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS group_message_reads(
			id INT AUTO_INCREMENT PRIMARY KEY,
			message_id INT NOT NULL,
			user_id INT NOT NULL,
			read_at DATETIME DEFAULT CURRENT_TIMESTAMP,
			UNIQUE KEY uq_group_message_reads_pair(message_id, user_id),
			KEY idx_group_message_reads_message(message_id),
			KEY idx_group_message_reads_user(user_id),
			CONSTRAINT fk_group_message_reads_message FOREIGN KEY(message_id) REFERENCES group_messages(id),
			CONSTRAINT fk_group_message_reads_user FOREIGN KEY(user_id) REFERENCES users(id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		""",
		"""
		CREATE TABLE IF NOT EXISTS risk_records(
			id INT AUTO_INCREMENT PRIMARY KEY,
			username VARCHAR(255) NOT NULL DEFAULT '',
			user_id INT DEFAULT 0,
			risk_level VARCHAR(64) NOT NULL,
			source_type VARCHAR(64) NOT NULL,
			source_name VARCHAR(255) DEFAULT '',
			risk_keywords TEXT,
			keyword_count INT DEFAULT 0,
			risk_score INT DEFAULT 0,
			content_preview TEXT,
			ref_id INT DEFAULT 0,
			create_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
			UNIQUE KEY uq_risk_records_source_ref(source_type, ref_id)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
		"""
	]
	for s in stmts:
		conn.execute(s)

def _ensure_chat_messages_content_type(conn):
	try:
		if get_db_type() == "mysql":
			cursor = conn.execute("PRAGMA table_info(chat_messages)")
			rows = cursor.fetchall()
			for row in rows:
				col_name = row[1]
				col_type = str(row[2] or "").upper()
				if col_name == "content" and "TEXT" not in col_type:
					try:
						conn.execute("ALTER TABLE chat_messages MODIFY COLUMN content TEXT NOT NULL")
						conn.commit()
					except Exception:
						pass
					break
		else:
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
					except Exception:
						try:
							conn.execute("ALTER TABLE chat_messages_old RENAME TO chat_messages")
						except Exception:
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
				if get_db_type() == "mysql":
					conn.execute("ALTER TABLE chat_conversations ADD COLUMN is_pinned INT NOT NULL DEFAULT 0")
				else:
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
				if get_db_type() == "mysql":
					conn.execute("ALTER TABLE friends ADD COLUMN status VARCHAR(32) DEFAULT 'pending'")
				else:
					conn.execute("ALTER TABLE friends ADD COLUMN status TEXT DEFAULT 'pending'")
				conn.commit()
			except Exception:
				pass
	except Exception:
		pass

def _ensure_columns_exist(conn):
	try:
		cursor = conn.execute("PRAGMA table_info(users)")
		existing_cols = {row[1] for row in cursor.fetchall()}
		if "real_name" not in existing_cols:
			try:
				if get_db_type() == "mysql":
					conn.execute("ALTER TABLE users ADD COLUMN real_name VARCHAR(255) DEFAULT ''")
				else:
					conn.execute("ALTER TABLE users ADD COLUMN real_name TEXT DEFAULT ''")
				conn.commit()
			except Exception:
				pass
		if "email" not in existing_cols:
			try:
				if get_db_type() == "mysql":
					conn.execute("ALTER TABLE users ADD COLUMN email VARCHAR(255) DEFAULT ''")
				else:
					conn.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")
				conn.commit()
			except Exception:
				pass
		if "phone" not in existing_cols:
			try:
				if get_db_type() == "mysql":
					conn.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(255) DEFAULT ''")
				else:
					conn.execute("ALTER TABLE users ADD COLUMN phone TEXT DEFAULT ''")
				conn.commit()
			except Exception:
				pass
		if "status" not in existing_cols:
			try:
				if get_db_type() == "mysql":
					conn.execute("ALTER TABLE users ADD COLUMN status INT DEFAULT 1")
				else:
					conn.execute("ALTER TABLE users ADD COLUMN status INTEGER DEFAULT 1")
				conn.commit()
			except Exception:
				pass
		if "update_at" not in existing_cols:
			try:
				if get_db_type() == "mysql":
					conn.execute("ALTER TABLE users ADD COLUMN update_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP")
					conn.execute("UPDATE users SET update_at = NOW()")
				else:
					conn.execute("ALTER TABLE users ADD COLUMN update_at TEXT")
					conn.execute("UPDATE users SET update_at = datetime('now')")
				conn.commit()
			except Exception:
				pass
	finally:
		pass

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
