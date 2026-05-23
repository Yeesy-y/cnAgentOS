# 数据库链接与建表
import os
import sqlite3

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
	with get_connection() as conn:
		conn.execute(
			"""
			CREATE TABLE IF NOT EXISTS users(
				id integer PRIMARY KEY AUTOINCREMENT,
				username TEXT NOT NULL UNIQUE,
				password_hash TEXT NOT NULL,
				salt TEXT NOT NULL,
				create_at TEXT NOT NULL DEFAULT(datetime('now'))
			)
			"""
		)
