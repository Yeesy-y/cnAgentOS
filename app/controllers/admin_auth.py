import tornado.web

from app.controllers.admin_base import AdminBaseHandler
from app.models.admin_user import AdminUserRepository

class AdminLoginHandler(AdminBaseHandler):
	def get(self):
		self.render("admin_login.html", title="管理后台登录", error=None)

	def post(self):
		username = (self.get_body_argument("username", "") or "").strip()
		password = self.get_body_argument("password", "")

		if not username or not password:
			return self.render("admin_login.html", title="管理后台登录", error="用户名或密码不能为空")

		user = AdminUserRepository.get_user_by_username(username)
		if not user:
			return self.render("admin_login.html", title="管理后台登录", error="用户不存在")

		try:
			user_status = user["status"]
			if user_status != 1:
				return self.render("admin_login.html", title="管理后台登录", error="该账号已被禁用，请联系管理员")
		except (IndexError, KeyError):
			pass

		if not AdminUserRepository.verify_user(username, password):
			return self.render("admin_login.html", title="管理后台登录", error="用户名或密码错误")

		self.set_secure_cookie("admin_username", username)
		self.redirect("/admin/index")


class AdminLogoutHandler(AdminBaseHandler):
	def post(self):
		self.clear_cookie("admin_username")
		self.redirect("/admin/login")
