import json
import tornado.web
from app.controllers.admin_base import AdminBaseHandler
from app.models.api_service import ApiEndpointRepository

class AdminApiListHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		page = int(self.get_argument("page", "1"))
		keyword = (self.get_argument("keyword", "") or "").strip()
		result = ApiEndpointRepository.list_apis(page, 20, keyword)
		self.render("admin_api_list.html",
			title="接口管理",
			username=self.current_user,
			active_menu="api",
			apis=result["data"],
			total=result["total"],
			page=result["page"],
			page_size=result["page_size"],
			keyword=keyword)

	def post(self):
		action = self.get_body_argument("action", "")
		if action == "delete":
			api_id_str = self.get_body_argument("api_id", "")
			if api_id_str and api_id_str.isdigit():
				ApiEndpointRepository.delete_api(int(api_id_str))
		return self.redirect("/admin/api/list")


class AdminApiAddHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		self.render("admin_api_form.html",
			title="新增接口",
			username=self.current_user,
			active_menu="api",
			api=None,
			mode="add",
			error=None)

	def post(self):
		api_name = (self.get_body_argument("api_name", "") or "").strip()
		api_code = (self.get_body_argument("api_code", "") or "").strip()
		api_url = (self.get_body_argument("api_url", "") or "").strip()
		request_method = (self.get_body_argument("request_method", "GET") or "GET").strip().upper()
		response_format = (self.get_body_argument("response_format", "JSON") or "JSON").strip().upper()
		qps_limit = (self.get_body_argument("qps_limit", "") or "").strip()
		token = (self.get_body_argument("token", "") or "").strip()
		remark = (self.get_body_argument("remark", "") or "").strip()

		if not api_name or not api_code or not api_url:
			self.render("admin_api_form.html",
				title="新增接口",
				username=self.current_user,
				active_menu="api",
				api={"api_name": api_name, "api_code": api_code, "api_url": api_url, "request_method": request_method, "response_format": response_format, "qps_limit": qps_limit, "token": token, "remark": remark, "status": 1},
				mode="add",
				error="接口名称/编码/URL 不能为空")
			return

		api_id = ApiEndpointRepository.create_api(api_name, api_code, api_url, request_method, response_format, qps_limit, token, remark, 1)
		if not api_id:
			self.render("admin_api_form.html",
				title="新增接口",
				username=self.current_user,
				active_menu="api",
				api={"api_name": api_name, "api_code": api_code, "api_url": api_url, "request_method": request_method, "response_format": response_format, "qps_limit": qps_limit, "token": token, "remark": remark, "status": 1},
				mode="add",
				error="创建失败：接口编码可能已存在")
			return
		return self.redirect("/admin/api/list")


class AdminApiEditHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def get(self):
		api_id = int(self.get_argument("id", "0"))
		if not api_id:
			return self.redirect("/admin/api/list")
		api = ApiEndpointRepository.get_api_by_id(api_id)
		if not api:
			return self.redirect("/admin/api/list")
		self.render("admin_api_form.html",
			title="编辑接口",
			username=self.current_user,
			active_menu="api",
			api=api,
			mode="edit",
			error=None)

	def post(self):
		api_id = int(self.get_body_argument("id", "0"))
		if not api_id:
			return self.redirect("/admin/api/list")

		api_name = (self.get_body_argument("api_name", "") or "").strip()
		api_code = (self.get_body_argument("api_code", "") or "").strip()
		api_url = (self.get_body_argument("api_url", "") or "").strip()
		request_method = (self.get_body_argument("request_method", "GET") or "GET").strip().upper()
		response_format = (self.get_body_argument("response_format", "JSON") or "JSON").strip().upper()
		qps_limit = (self.get_body_argument("qps_limit", "") or "").strip()
		token = (self.get_body_argument("token", "") or "").strip()
		remark = (self.get_body_argument("remark", "") or "").strip()
		status = int(self.get_body_argument("status", "1"))

		if not api_name or not api_code or not api_url:
			self.render("admin_api_form.html",
				title="编辑接口",
				username=self.current_user,
				active_menu="api",
				api={"id": api_id, "api_name": api_name, "api_code": api_code, "api_url": api_url, "request_method": request_method, "response_format": response_format, "qps_limit": qps_limit, "token": token, "remark": remark, "status": status},
				mode="edit",
				error="接口名称/编码/URL 不能为空")
			return

		ok = ApiEndpointRepository.update_api(
			api_id,
			api_name=api_name,
			api_code=api_code,
			api_url=api_url,
			request_method=request_method,
			response_format=response_format,
			qps_limit=qps_limit,
			token=token,
			remark=remark,
			status=status
		)
		if not ok:
			self.render("admin_api_form.html",
				title="编辑接口",
				username=self.current_user,
				active_menu="api",
				api={"id": api_id, "api_name": api_name, "api_code": api_code, "api_url": api_url, "request_method": request_method, "response_format": response_format, "qps_limit": qps_limit, "token": token, "remark": remark, "status": status},
				mode="edit",
				error="保存失败：接口编码可能已存在")
			return
		return self.redirect("/admin/api/list")


class AdminApiTestHandler(AdminBaseHandler):
	@tornado.web.authenticated
	def post(self):
		self.set_header("Content-Type", "application/json")
		api_id_str = self.get_body_argument("api_id", "")
		params_json = self.get_body_argument("params_json", "")
		timeout = int(self.get_body_argument("timeout", "30"))

		if not api_id_str or not api_id_str.isdigit():
			self.write(json.dumps({"success": False, "message": "参数错误：api_id"}))
			return

		api = ApiEndpointRepository.get_api_by_id(int(api_id_str))
		if not api:
			self.write(json.dumps({"success": False, "message": "接口不存在"}))
			return

		params = {}
		if params_json:
			try:
				params = json.loads(params_json)
				if params is None:
					params = {}
				if not isinstance(params, dict):
					self.write(json.dumps({"success": False, "message": "参数必须为JSON对象"}))
					return
			except Exception:
				self.write(json.dumps({"success": False, "message": "参数JSON解析失败"}))
				return

		timeout = max(1, min(timeout, 120))
		result = ApiEndpointRepository.call_api(api.get("api_code", ""), params=params, timeout=timeout)
		self.write(json.dumps(result, ensure_ascii=False))
