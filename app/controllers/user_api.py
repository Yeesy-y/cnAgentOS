import json
import tornado.web
from app.controllers.user_base import UserBaseHandler
from app.models.chat_service import ChatRepository, ChatRuntime, ModelRuntime, ChatOrchestrator

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
			data.append({"id": c.get("id"), "title": c.get("title") or "", "update_at": c.get("update_at")})
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
		task = ChatRuntime.create_stream_task(user_id, conversation_id, message, model_service_id)
		stream_url = "/user/api/stream?token=" + task["token"]
		self.write(json.dumps({"success": True, "conversation_id": conversation_id, "stream_url": stream_url}, ensure_ascii=False))

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
		conv = ChatRepository.get_conversation(conversation_id)
		if conv:
			model_service_id = int(conv.get("model_service_id") or model_service_id or 0)

		model = ModelRuntime.resolve_model(model_service_id)
		self.set_header("Content-Type", "text/event-stream; charset=utf-8")
		self.set_header("Cache-Control", "no-cache")
		self.set_header("Connection", "keep-alive")

		if not model:
			self.write("data: " + "未配置默认模型，请先到管理后台【模型引擎】添加并设为默认" + "\n\n")
			self.write("data: [DONE]\n\n")
			self.finish()
			return

		full = ""
		try:
			for chunk in ChatOrchestrator.generate_stream(model, message):
				full += chunk
				self.write("data: " + chunk.replace("\r", "") + "\n\n")
				await self.flush()
		except Exception as e:
			err = str(e) or "请求失败"
			self.write("data: " + ("\\n\\n**错误**：" + err) + "\n\n")
			await self.flush()
		finally:
			if full.strip():
				ChatRepository.create_message(conversation_id, "assistant", full)
			self.write("data: [DONE]\n\n")
			self.finish()
