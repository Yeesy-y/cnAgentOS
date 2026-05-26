import json
import tornado.web

from app.controllers.admin_base import AdminBaseHandler
from app.models.digital_employee import DigitalEmployeeRepository
from app.models.model_service import ModelServiceRepository
from app.models.api_service import ApiEndpointRepository


class AdminEmployeeListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		page = int(self.get_argument("page", "1"))
		keyword = (self.get_argument("keyword", "") or "").strip()
		result = DigitalEmployeeRepository.list_employees(page, 20, keyword)
		for e in result["data"]:
			ca = e.get("create_at") or ""
			if ca and len(ca) > 10:
				e["create_at"] = ca[:10] + " " + ca[11:19]
		self.render(
			"admin_employee_list.html",
			title="数字员工",
			username=self.current_user,
			active_menu="employee",
			employees=result["data"],
			total=result["total"],
			page=result["page"],
			page_size=result["page_size"],
			keyword=keyword
		)

	def post(self):
		action = self.get_body_argument("action", "")
		if action == "delete":
			employee_id_str = self.get_body_argument("employee_id", "")
			if employee_id_str and employee_id_str.isdigit():
				DigitalEmployeeRepository.delete_employee(int(employee_id_str))
		return self.redirect("/admin/employee/list")


class AdminEmployeeAddHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		models = ModelServiceRepository.list_models(1, 200).get("data") or []
		apis = ApiEndpointRepository.list_apis(1, 200, "").get("data") or []
		self.render(
			"admin_employee_form.html",
			title="新增数字员工",
			username=self.current_user,
			active_menu="employee",
			employee=None,
			mode="add",
			error="",
			models=models,
			apis=apis,
			config_json_pretty=""
		)

	def post(self):
		employee_name = (self.get_body_argument("employee_name", "") or "").strip()
		employee_code = (self.get_body_argument("employee_code", "") or "").strip()
		at_alias = (self.get_body_argument("at_alias", "") or "").strip()
		category = int(self.get_body_argument("category", "1"))
		service_type = (self.get_body_argument("service_type", "LLM") or "").strip().upper()
		description = (self.get_body_argument("description", "") or "").strip()
		model_code = (self.get_body_argument("model_code", "") or "").strip()
		prompt = (self.get_body_argument("prompt", "") or "").strip()
		api_code = (self.get_body_argument("api_code", "") or "").strip()
		config_json_text = (self.get_body_argument("config_json", "") or "").strip()

		if not employee_name or not employee_code or not at_alias:
			return self._render_error("请填写：员工名称 / 员工编码 / @别名", None, "add", config_json_text)
		if service_type == "LLM":
			if not prompt:
				return self._render_error("模型对话类型必须填写提示词（Prompt）", None, "add", config_json_text)
		elif service_type == "API":
			if not api_code:
				return self._render_error("API服务类型必须选择/填写 API 编码", None, "add", config_json_text)
		else:
			return self._render_error("服务类型不合法", None, "add", config_json_text)

		if config_json_text:
			try:
				json.loads(config_json_text)
			except Exception:
				return self._render_error("配置JSON格式不正确", None, "add", config_json_text)

		new_id = DigitalEmployeeRepository.create_employee(
			employee_name=employee_name,
			employee_code=employee_code,
			at_alias=at_alias,
			category=category,
			service_type=service_type,
			description=description,
			model_code=model_code if service_type == "LLM" else "",
			prompt=prompt if service_type == "LLM" else "",
			api_code=api_code if service_type == "API" else "",
			config_json=config_json_text,
			status=1
		)
		if not new_id:
			return self._render_error("保存失败：员工编码或@别名可能已存在", None, "add", config_json_text)
		return self.redirect("/admin/employee/list")

	def _render_error(self, error: str, employee: dict, mode: str, config_json_text: str):
		models = ModelServiceRepository.list_models(1, 200).get("data") or []
		apis = ApiEndpointRepository.list_apis(1, 200, "").get("data") or []
		config_json_pretty = config_json_text
		if config_json_text:
			try:
				config_json_pretty = json.dumps(json.loads(config_json_text), ensure_ascii=False, indent=2)
			except Exception:
				config_json_pretty = config_json_text
		self.render(
			"admin_employee_form.html",
			title="新增数字员工" if mode == "add" else "编辑数字员工",
			username=self.current_user,
			active_menu="employee",
			employee=employee,
			mode=mode,
			error=error,
			models=models,
			apis=apis,
			config_json_pretty=config_json_pretty
		)


class AdminEmployeeEditHandler(AdminEmployeeAddHandler):
	@tornado.web.authenticated
	def get(self):
		employee_id = int(self.get_argument("id", "0"))
		if not employee_id:
			return self.redirect("/admin/employee/list")
		employee = DigitalEmployeeRepository.get_by_id(employee_id)
		if not employee:
			return self.redirect("/admin/employee/list")

		models = ModelServiceRepository.list_models(1, 200).get("data") or []
		apis = ApiEndpointRepository.list_apis(1, 200, "").get("data") or []
		config_json_pretty = (employee.get("config_json") or "").strip()
		if config_json_pretty:
			try:
				config_json_pretty = json.dumps(json.loads(config_json_pretty), ensure_ascii=False, indent=2)
			except Exception:
				pass
		self.render(
			"admin_employee_form.html",
			title="编辑数字员工",
			username=self.current_user,
			active_menu="employee",
			employee=employee,
			mode="edit",
			error="",
			models=models,
			apis=apis,
			config_json_pretty=config_json_pretty
		)

	@tornado.web.authenticated
	def post(self):
		employee_id = int(self.get_body_argument("id", "0"))
		if not employee_id:
			return self.redirect("/admin/employee/list")
		existing = DigitalEmployeeRepository.get_by_id(employee_id)
		if not existing:
			return self.redirect("/admin/employee/list")

		employee_name = (self.get_body_argument("employee_name", "") or "").strip()
		employee_code = (self.get_body_argument("employee_code", "") or "").strip()
		at_alias = (self.get_body_argument("at_alias", "") or "").strip()
		category = int(self.get_body_argument("category", "1"))
		service_type = (self.get_body_argument("service_type", "LLM") or "").strip().upper()
		description = (self.get_body_argument("description", "") or "").strip()
		model_code = (self.get_body_argument("model_code", "") or "").strip()
		prompt = (self.get_body_argument("prompt", "") or "").strip()
		api_code = (self.get_body_argument("api_code", "") or "").strip()
		config_json_text = (self.get_body_argument("config_json", "") or "").strip()
		status = int(self.get_body_argument("status", "1"))

		if not employee_name or not employee_code or not at_alias:
			return self._render_error("请填写：员工名称 / 员工编码 / @别名", existing, "edit", config_json_text)
		if service_type == "LLM":
			if not prompt:
				return self._render_error("模型对话类型必须填写提示词（Prompt）", existing, "edit", config_json_text)
		elif service_type == "API":
			if not api_code:
				return self._render_error("API服务类型必须选择/填写 API 编码", existing, "edit", config_json_text)
		else:
			return self._render_error("服务类型不合法", existing, "edit", config_json_text)

		if config_json_text:
			try:
				json.loads(config_json_text)
			except Exception:
				return self._render_error("配置JSON格式不正确", existing, "edit", config_json_text)

		ok = DigitalEmployeeRepository.update_employee(
			employee_id,
			employee_name=employee_name,
			employee_code=employee_code,
			at_alias=at_alias,
			category=category,
			service_type=service_type,
			description=description,
			model_code=model_code if service_type == "LLM" else "",
			prompt=prompt if service_type == "LLM" else "",
			api_code=api_code if service_type == "API" else "",
			config_json=config_json_text,
			status=status
		)
		if not ok:
			return self._render_error("保存失败：员工编码或@别名可能已存在", existing, "edit", config_json_text)
		return self.redirect("/admin/employee/list")
