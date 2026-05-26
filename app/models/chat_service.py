import json
import secrets
import sqlite3
import time
import requests
from app.models.db import get_connection
from app.models.model_service import ModelServiceRepository

_STREAM_TASKS = {}
_CHAT_MESSAGES_LINK_COL = None

def _now_title(text: str) -> str:
	text = (text or "").strip()
	if not text:
		return "新对话"
	return text[:20]

def _build_chat_url(base_url: str) -> str:
	base = (base_url or "").rstrip("/")
	if base.endswith("/chat/completions"):
		return base
	if base.endswith("/v1"):
		return base + "/chat/completions"
	return base + "/v1/chat/completions"

def _safe_select_sql(sql: str) -> str:
	s = (sql or "").strip()
	if not s:
		raise ValueError("SQL为空")
	s_l = s.lower()
	for bad in [";", "pragma", "attach", "detach", "drop ", "delete ", "update ", "insert ", "alter ", "create ", "replace "]:
		if bad in s_l:
			raise ValueError("SQL包含不允许的语句")
	if not s_l.startswith("select"):
		raise ValueError("仅允许SELECT查询")
	if " limit " not in s_l:
		s = s.rstrip() + " LIMIT 50"
	return s

def _chat_messages_link_column(conn) -> str:
	global _CHAT_MESSAGES_LINK_COL
	if _CHAT_MESSAGES_LINK_COL:
		return _CHAT_MESSAGES_LINK_COL
	try:
		cols = [r[1] for r in conn.execute("PRAGMA table_info(chat_messages)").fetchall()]
	except Exception:
		cols = []
	if "conversation_id" in cols:
		_CHAT_MESSAGES_LINK_COL = "conversation_id"
	elif "session_id" in cols:
		_CHAT_MESSAGES_LINK_COL = "session_id"
	else:
		_CHAT_MESSAGES_LINK_COL = "conversation_id"
	return _CHAT_MESSAGES_LINK_COL

class ChatRepository:
	@staticmethod
	def create_conversation(user_id: int, title: str, model_service_id: int = 0) -> int:
		with get_connection() as conn:
			cursor = conn.execute(
				"INSERT INTO chat_conversations(user_id, title, model_service_id) VALUES(?,?,?)",
				(user_id, title or "", int(model_service_id or 0))
			)
			return cursor.lastrowid

	@staticmethod
	def touch_conversation(conversation_id: int):
		with get_connection() as conn:
			conn.execute("UPDATE chat_conversations SET update_at=datetime('now') WHERE id=?", (conversation_id,))

	@staticmethod
	def set_conversation_model(conversation_id: int, model_service_id: int):
		with get_connection() as conn:
			conn.execute(
				"UPDATE chat_conversations SET model_service_id=?, update_at=datetime('now') WHERE id=?",
				(int(model_service_id or 0), conversation_id)
			)

	@staticmethod
	def list_conversations(user_id: int, limit: int = 50) -> list:
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT * FROM chat_conversations WHERE user_id=? ORDER BY update_at DESC, id DESC LIMIT ?",
				(user_id, int(limit))
			).fetchall()
		return [dict(r) for r in rows]

	@staticmethod
	def get_conversation(conversation_id: int):
		with get_connection() as conn:
			row = conn.execute("SELECT * FROM chat_conversations WHERE id=?", (conversation_id,)).fetchone()
		return dict(row) if row else None

	@staticmethod
	def create_message(conversation_id: int, role: str, content: str) -> int:
		with get_connection() as conn:
			link_col = _chat_messages_link_column(conn)
			cursor = conn.execute(
				f"INSERT INTO chat_messages({link_col}, role, content) VALUES(?,?,?)",
				(conversation_id, role, content)
			)
			conn.execute("UPDATE chat_conversations SET update_at=datetime('now') WHERE id=?", (conversation_id,))
			return cursor.lastrowid

	@staticmethod
	def list_messages(conversation_id: int, limit: int = 200) -> list:
		with get_connection() as conn:
			link_col = _chat_messages_link_column(conn)
			rows = conn.execute(
				f"SELECT role, content, create_at FROM chat_messages WHERE {link_col}=? ORDER BY id ASC LIMIT ?",
				(conversation_id, int(limit))
			).fetchall()
		return [dict(r) for r in rows]

class ChatRuntime:
	@staticmethod
	def create_stream_task(user_id: int, conversation_id: int, message: str, model_service_id: int = 0) -> dict:
		token = secrets.token_urlsafe(16)
		_STREAM_TASKS[token] = {
			"user_id": int(user_id),
			"conversation_id": int(conversation_id),
			"message": message,
			"model_service_id": int(model_service_id or 0),
			"create_ts": time.time(),
		}
		return {"token": token}

	@staticmethod
	def pop_stream_task(token: str):
		return _STREAM_TASKS.pop(token, None)

class ModelRuntime:
	@staticmethod
	def list_enabled_models() -> list:
		with get_connection() as conn:
			rows = conn.execute(
				"SELECT * FROM model_services WHERE status=1 ORDER BY is_default DESC, id DESC"
			).fetchall()
		return [dict(r) for r in rows]

	@staticmethod
	def resolve_model(model_service_id: int = 0):
		if model_service_id:
			return ModelServiceRepository.get_model_by_id(int(model_service_id))
		return ModelServiceRepository.get_default_model()

class LlmRuntime:
	@staticmethod
	def _chat_once(model: dict, messages: list, stream: bool):
		headers = {"Content-Type": "application/json"}
		api_key = (model.get("api_key") or "").strip()
		if api_key:
			headers["Authorization"] = f"Bearer {api_key}"
		url = _build_chat_url(model.get("base_url") or "")
		data = {
			"model": model.get("model_id"),
			"messages": messages,
			"stream": bool(stream),
		}
		return requests.post(url, headers=headers, json=data, timeout=60, stream=stream)

	@staticmethod
	def decide_tool(model: dict, user_message: str) -> dict:
		prompt = [
			{"role": "system", "content": "你是一个意图识别器。判断用户问题是否需要查询SQLite数据仓库。若需要，请只输出JSON：{\"tool\":\"sql\",\"query\":\"SELECT ...\"}；否则只输出JSON：{\"tool\":\"none\"}。仅允许SELECT，表仅允许 watch_data, watch_sources。"},
			{"role": "user", "content": user_message},
		]
		resp = LlmRuntime._chat_once(model, prompt, stream=False)
		resp.raise_for_status()
		data = resp.json()
		content = data["choices"][0]["message"]["content"]
		try:
			obj = json.loads(content)
			if isinstance(obj, dict):
				return obj
		except Exception:
			pass
		return {"tool": "none"}

	@staticmethod
	def run_sql(query: str) -> dict:
		sql = _safe_select_sql(query)
		sql_l = sql.lower()
		allowed_tables = ["watch_data", "watch_sources"]
		if not any(t in sql_l for t in allowed_tables):
			raise ValueError("仅允许查询 watch_data / watch_sources")
		with get_connection() as conn:
			rows = conn.execute(sql).fetchall()
		return {"sql": sql, "rows": [dict(r) for r in rows]}

	@staticmethod
	def stream_answer(model: dict, user_message: str, tool_result: dict = None):
		system_prompt = "你是AI智能瞭望与智能问数系统的助手。回答要简洁、可读，使用Markdown。"
		messages = [{"role": "system", "content": system_prompt}]
		if tool_result is not None:
			messages.append({"role": "system", "content": "已获取数据库查询结果（JSON）：\n" + json.dumps(tool_result, ensure_ascii=False)})
		messages.append({"role": "user", "content": user_message})

		resp = LlmRuntime._chat_once(model, messages, stream=True)
		resp.raise_for_status()
		full_text = ""
		for raw in resp.iter_lines(decode_unicode=True):
			if not raw:
				continue
			line = raw.strip()
			if not line.startswith("data:"):
				continue
			payload = line[5:].strip()
			if payload == "[DONE]":
				break
			try:
				obj = json.loads(payload)
				delta = obj["choices"][0]["delta"].get("content")
				if delta:
					full_text += delta
					yield delta
			except Exception:
				continue
		return full_text

class ChatOrchestrator:
	@staticmethod
	def generate_stream(model: dict, message: str):
		tool = LlmRuntime.decide_tool(model, message)
		if tool.get("tool") == "sql":
			result = LlmRuntime.run_sql(tool.get("query", ""))
			for chunk in LlmRuntime.stream_answer(model, message, tool_result=result):
				yield chunk
			return
		for chunk in LlmRuntime.stream_answer(model, message, tool_result=None):
			yield chunk
