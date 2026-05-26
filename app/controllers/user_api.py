import json
import re
import tornado.web
from app.controllers.user_base import UserBaseHandler
from app.models.chat_service import ChatRepository, ChatRuntime, ModelRuntime, ChatOrchestrator, EmployeeOrchestrator
from app.models.digital_employee import DigitalEmployeeRepository

class UserModelsHandler(UserBaseHandler):
	def get(self):
		self.set_header("Content-Type", "application/json")
		models = ModelRuntime.list_enabled_models()
		data = []
		for m in models:
			data.append({
				"id": m.get("id"),
				"model_name": m.get("model_name"),
				"model_code": m.get("model_code"),
				"is_default": int(m.get("is_default") or 0),
			})
		self.write(json.dumps({"success": True, "data": data}, ensure_ascii=False))

class UserConversationsHandler(UserBaseHandler):
	def get(self):
		self.set_header("Content-Type", "application/json")
		user = self.get_current_user_row()
		if not user:
			self.set_status(401)
			self.write(json.dumps({"success": False, "message": "未登录"}))
			return
		user_id = int(user["id"])
		convs = ChatRepository.list_conversations(user_id, 50)
		data = []
		for c in convs:
			data.append({
				"id": c.get("id"),
				"title": c.get("title") or "",
				"update_at": c.get("update_at"),
				"is_pinned": int(c.get("is_pinned") or 0),
			})
		self.write(json.dumps({"success": True, "data": data}, ensure_ascii=False))

class UserMessagesHandler(UserBaseHandler):
	def get(self):
		self.set_header("Content-Type", "application/json")
		user = self.get_current_user_row()
		if not user:
			self.set_status(401)
			self.write(json.dumps({"success": False, "message": "未登录"}))
			return
		user_id = int(user["id"])
		conversation_id = int(self.get_argument("conversation_id", "0"))
		if not conversation_id:
			self.write(json.dumps({"success": False, "message": "参数错误"}))
			return
		conv = ChatRepository.get_conversation(conversation_id)
		if not conv or int(conv.get("user_id") or 0) != user_id:
			self.write(json.dumps({"success": False, "message": "无权限"}))
			return
		msgs = ChatRepository.list_messages(conversation_id, 200)
		self.write(json.dumps({"success": True, "data": msgs}, ensure_ascii=False))

class UserSendHandler(UserBaseHandler):
	def post(self):
		self.set_header("Content-Type", "application/json")
		user = self.get_current_user_row()
		if not user:
			self.set_status(401)
			self.write(json.dumps({"success": False, "message": "未登录"}))
			return
		user_id = int(user["id"])

		message = (self.get_body_argument("message", "") or "").strip()
		conversation_id = int(self.get_body_argument("conversation_id", "0"))
		model_service_id = int(self.get_body_argument("model_service_id", "0"))

		if not message:
			self.write(json.dumps({"success": False, "message": "消息不能为空"}))
			return

		is_employee = False
		employee_id = 0
		employee_text = ""
		if message.startswith("@"):
			m = re.match(r"^@([^\s:：]+)(?:[:：\s]+(.*))?$", message)
			if m:
				alias = (m.group(1) or "").strip()
				employee_text = (m.group(2) or "").strip()
				employee = DigitalEmployeeRepository.get_by_alias(alias)
				if not employee:
					self.write(json.dumps({"success": False, "message": "未找到数字员工：@" + alias}, ensure_ascii=False))
					return
				if int(employee.get("status") or 0) != 1:
					self.write(json.dumps({"success": False, "message": "该数字员工已禁用：@" + alias}, ensure_ascii=False))
					return
				is_employee = True
				employee_id = int(employee.get("id") or 0)

		if conversation_id:
			conv = ChatRepository.get_conversation(conversation_id)
			if not conv or int(conv.get("user_id") or 0) != user_id:
				self.write(json.dumps({"success": False, "message": "无权限"}))
				return
		else:
			title = message[:20]
			conversation_id = ChatRepository.create_conversation(user_id, title, model_service_id)

		if model_service_id:
			ChatRepository.set_conversation_model(conversation_id, model_service_id)

		ChatRepository.create_message(conversation_id, "user", message)
		extra = {}
		if is_employee and employee_id:
			extra["employee_id"] = employee_id
			extra["employee_text"] = employee_text
		task = ChatRuntime.create_stream_task(user_id, conversation_id, message, model_service_id, extra=extra)
		stream_url = "/user/api/stream?token=" + task["token"]
		self.write(json.dumps({"success": True, "conversation_id": conversation_id, "stream_url": stream_url}, ensure_ascii=False))

class UserConversationActionHandler(UserBaseHandler):
	def post(self):
		self.set_header("Content-Type", "application/json")
		user = self.get_current_user_row()
		if not user:
			self.set_status(401)
			self.write(json.dumps({"success": False, "message": "未登录"}))
			return
		user_id = int(user["id"])

		action = (self.get_body_argument("action", "") or "").strip()
		conversation_id = int(self.get_body_argument("conversation_id", "0"))
		if not conversation_id:
			self.write(json.dumps({"success": False, "message": "参数错误"}))
			return
		conv = ChatRepository.get_conversation(conversation_id)
		if not conv or int(conv.get("user_id") or 0) != user_id:
			self.write(json.dumps({"success": False, "message": "无权限"}))
			return

		if action == "pin":
			ChatRepository.set_pinned(conversation_id, 1)
			self.write(json.dumps({"success": True}, ensure_ascii=False))
			return
		if action == "unpin":
			ChatRepository.set_pinned(conversation_id, 0)
			self.write(json.dumps({"success": True}, ensure_ascii=False))
			return
		if action == "rename":
			title = (self.get_body_argument("title", "") or "").strip()
			if not title:
				self.write(json.dumps({"success": False, "message": "标题不能为空"}))
				return
			if len(title) > 50:
				title = title[:50]
			ChatRepository.update_title(conversation_id, title)
			self.write(json.dumps({"success": True}, ensure_ascii=False))
			return
		if action == "delete":
			ChatRepository.delete_conversation(conversation_id)
			self.write(json.dumps({"success": True}, ensure_ascii=False))
			return
		if action == "report":
			self.write(json.dumps({"success": True}, ensure_ascii=False))
			return

		self.write(json.dumps({"success": False, "message": "不支持的操作"}))

class UserStreamHandler(UserBaseHandler):
	async def get(self):
		user = self.get_current_user_row()
		if not user:
			self.set_status(401)
			return
		user_id = int(user["id"])

		token = (self.get_argument("token", "") or "").strip()
		task = ChatRuntime.pop_stream_task(token)
		if not task or int(task.get("user_id") or 0) != user_id:
			self.set_status(403)
			return

		conversation_id = int(task.get("conversation_id") or 0)
		message = task.get("message") or ""
		model_service_id = int(task.get("model_service_id") or 0)
		employee_id = int(task.get("employee_id") or 0)
		employee_text = (task.get("employee_text") or "").strip()
		conv = ChatRepository.get_conversation(conversation_id)
		if conv:
			model_service_id = int(conv.get("model_service_id") or model_service_id or 0)

		self.set_header("Content-Type", "text/event-stream; charset=utf-8")
		self.set_header("Cache-Control", "no-cache")
		self.set_header("Connection", "keep-alive")

		def write_sse(text: str):
			payload = (text or "").replace("\r", "")
			for line in payload.split("\n"):
				self.write("data: " + line + "\n")
			self.write("\n")

		full = ""
		try:
			if employee_id:
				employee = DigitalEmployeeRepository.get_by_id(employee_id)
				for chunk in EmployeeOrchestrator.generate_employee_stream(employee, employee_text, model_service_id):
					full += chunk
					write_sse(chunk)
					await self.flush()
			else:
				model = ModelRuntime.resolve_model(model_service_id)
				if not model:
					msg = "未配置默认模型，请先到管理后台【模型引擎】添加并设为默认"
					full += msg
					write_sse(msg)
					return
				for chunk in ChatOrchestrator.generate_stream(model, message):
					full += chunk
					write_sse(chunk)
					await self.flush()
		except Exception as e:
			err = str(e) or "请求失败"
			write_sse("\\n\\n**错误**：" + err)
			await self.flush()
		finally:
			if full.strip():
				ChatRepository.create_message(conversation_id, "assistant", full)
			write_sse("[DONE]")
			self.finish()
