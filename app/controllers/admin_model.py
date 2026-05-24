import tornado.web
import json
import requests
from app.controllers.admin_base import AdminBaseHandler
from app.models.model_service import ModelServiceRepository

class AdminModelListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		page = int(self.get_argument("page", "1"))
		result = ModelServiceRepository.list_models(page, 6)
		for m in result["data"]:
			if "create_at" in m and m["create_at"]:
				ca = m["create_at"]
				if len(ca) > 10:
					m["create_at"] = ca[:10] + " " + ca[11:19]
		self.render("admin_model_list.html",
			title="模型引擎",
			username=self.current_user,
			active_menu="model",
			models=result["data"],
			total=result["total"],
			page=result["page"],
			page_size=result["page_size"])
	
	def post(self):
		action = self.get_body_argument("action", "")
		model_id_str = self.get_body_argument("model_id", "")
		if action == "delete" and model_id_str:
			model_id = int(model_id_str)
			ModelServiceRepository.delete_model(model_id)
		elif action == "set_default" and model_id_str:
			model_id = int(model_id_str)
			ModelServiceRepository.update_model(model_id, is_default=1)
		return self.redirect("/admin/model/list")

class AdminModelAddHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin_model_form.html",
			title="新增模型",
			username=self.current_user,
			active_menu="model",
			model=None,
			mode="add")
	
	def post(self):
		model_name = (self.get_body_argument("model_name", "") or "").strip()
		model_code = (self.get_body_argument("model_code", "") or "").strip()
		api_key = (self.get_body_argument("api_key", "") or "").strip()
		base_url = (self.get_body_argument("base_url", "") or "").strip()
		model_id_param = (self.get_body_argument("model_id", "") or "").strip()
		is_default = int(self.get_body_argument("is_default", "0"))
		
		if not model_name or not model_code or not api_key or not base_url or not model_id_param:
			return self.redirect("/admin/model/add")
		
		ModelServiceRepository.create_model(model_name, model_code, api_key, base_url, model_id_param, is_default)
		return self.redirect("/admin/model/list")

class AdminModelEditHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		model_id = int(self.get_argument("id", "0"))
		if not model_id:
			return self.redirect("/admin/model/list")
		model = ModelServiceRepository.get_model_by_id(model_id)
		if not model:
			return self.redirect("/admin/model/list")
		self.render("admin_model_form.html",
			title="编辑模型",
			username=self.current_user,
			active_menu="model",
			model=dict(model),
			mode="edit")
	
	def post(self):
		model_id = int(self.get_body_argument("id", "0"))
		if not model_id:
			return self.redirect("/admin/model/list")
		
		model_name = (self.get_body_argument("model_name", "") or "").strip()
		model_code = (self.get_body_argument("model_code", "") or "").strip()
		api_key = (self.get_body_argument("api_key", "") or "").strip()
		base_url = (self.get_body_argument("base_url", "") or "").strip()
		model_id_param = (self.get_body_argument("model_id", "") or "").strip()
		is_default = int(self.get_body_argument("is_default", "0"))
		status = int(self.get_body_argument("status", "1"))
		
		ModelServiceRepository.update_model(
			model_id,
			model_name=model_name,
			model_code=model_code,
			api_key=api_key,
			base_url=base_url,
			model_id_param=model_id_param,
			is_default=is_default,
			status=status
		)
		return self.redirect("/admin/model/list")

class AdminModelTestHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		model_id = int(self.get_body_argument("model_id", "0"))
		test_message = (self.get_body_argument("test_message", "") or "").strip()
		
		if not model_id or not test_message:
			self.write(json.dumps({"success": False, "message": "参数错误"}))
			return
		
		model = ModelServiceRepository.get_model_by_id(model_id)
		if not model:
			self.write(json.dumps({"success": False, "message": "模型不存在"}))
			return
		
		try:
			headers = {
				"Content-Type": "application/json",
				"Authorization": f"Bearer {model['api_key']}"
			}
			
			data = {
				"model": model["model_id"],
				"messages": [{"role": "user", "content": test_message}],
				"stream": False
			}
			
			base = model['base_url'].rstrip('/')
			if base.endswith('/chat/completions'):
				url = base
			elif base.endswith('/v1'):
				url = base + '/chat/completions'
			else:
				url = base + '/v1/chat/completions'
			
			response = requests.post(
				url,
				headers=headers,
				json=data,
				timeout=60
			)
			
			response.raise_for_status()
			result_data = response.json()
			
			result = result_data["choices"][0]["message"]["content"]
			tokens_used = result_data.get("usage", {}).get("total_tokens", 0)
			
			if tokens_used > 0:
				ModelServiceRepository.increment_token_usage(model_id, tokens_used)
			
			self.write(json.dumps({"success": True, "message": result, "tokens": tokens_used}))
		except requests.exceptions.HTTPError as e:
			err_text = ""
			try:
				err_json = e.response.json()
				err_text = err_json.get("error", {}).get("message", "") or str(err_json)
			except Exception:
				err_text = e.response.text if e.response is not None else str(e)
			self.write(json.dumps({"success": False, "message": f"请求失败: {e}. 详情: {err_text}"}))
		except requests.exceptions.RequestException as e:
			self.write(json.dumps({"success": False, "message": f"请求失败: {str(e)}"}))
		except Exception as e:
			self.write(json.dumps({"success": False, "message": str(e)}))
